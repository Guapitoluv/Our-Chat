import { InfiniteVideoBackground } from "./scripts/infinite-video-background.js";
import { UserProfileFlyout } from "./scripts/user-profile-flyout.js";
import { Search } from "./scripts/search.js";
import { Page } from "../../core/page/page.js";

// Mapa de comandos (suporta funções síncronas e assíncronas)
const commands = new Map([
    [
        "chat",
        (page) => {
            page.context.router.navigate("/conversation");
        }
    ],
    [
        "toggle_theme",
        (page) => {
            page.handleThemeToggle();
        }
    ],
    [
        "play",
        (page) => {
            page.handleMusic();
        }
    ],
    [
        "config",
        () => {}
    ],
    [
        "last",
        async (page) => {
            if (page.lastCommand) {
                await page.lastCommand(page);
            }
        }
    ],
    [
        "sign_up",
        (page) => {
            page.context.router.navigate("/sign-up");
        }
    ],
    [
        "sign_in",
        (page) => {
            page.context.router.navigate("/sign-in");
        }
    ],
    [
        "reconnect",
        async (page) => {
            await page.context.ws?.reconnect();
        }
    ],
    [
        "disconnect",
        (page) => {
            page.context.ws?.disconnect();
        }
    ],
    [
        "connect",
        async (page) => {
            await page.context.ws?.connect();
        }
    ]
]);

export class IndexPage extends Page {
    constructor() {
        super("./src/pages/index/index.html");
        
        this.background = null;
        this.consoleInput = null;
        this.commandList = null;
        
        this.search = new Search();
        
        this.commands = [...commands.keys()];
        this.pinnedCommands = new Set();
        
        this.floatingMenu = null;
        this.menuBtn = null;
        this.sidebar = null;
        this.closeSidebarBtn = null;
        this.connectionStatus = null;
        
        this.userFlyout = null;
        this.lastCommand = null;
        this.onStateChangeHandler = null;
    }

    mount(context) {
        super.mount(context);
        
        this.#getElements();
        this.#setEvents();
        
        this.createBackground();
        
        this.element.dataset.theme = "light";
        
        this.background?.start();
        
        // Configuração do Profile Flyout
        const flyoutContainer = this.element.querySelector(".user-profile-flyout");
        if (flyoutContainer) {
            this.userFlyout = new UserProfileFlyout(flyoutContainer);
            
            // Valida se o usuário está autenticado
            const currentUser = this.context.app?.user;
            if (currentUser && currentUser.id) {
                this.userFlyout.setUserData(currentUser);
            }
        }
    }
    
    #getElements() {
        this.consoleInput = this.element.querySelector("#console-input");
        this.commandList = this.element.querySelector("#command-list");
        this.floatingMenu = this.element.querySelector("#floating-menu");
        this.menuBtn = this.element.querySelector("#menu-image");
        this.sidebar = this.element.querySelector("#sidebar");
        this.closeSidebarBtn = this.element.querySelector("#close-sidebar");
        this.connectionStatus = this.element.querySelector("#connection-status");
    }

    #updateStatusUI(isConnected) {
        if (!this.connectionStatus) return;
        
        if (isConnected) {
            this.connectionStatus.classList.add("connected");
        } else {
            this.connectionStatus.classList.remove("connected");
        }
    }

    /**
     * Executa um comando de forma unificada (trata funções síncronas e Promises transparentemente)
     */
    async #executeCommand(commandKey, cmdFn) {
        if (!cmdFn) return;

        if (this.consoleInput) {
            this.consoleInput.value = "";
            this.#renderCommands(this.consoleInput.value);
        }

        if (commandKey !== "last") {
            this.lastCommand = cmdFn;
        }

        try {
            // await resolve comandos assíncronos e executa síncronos imediatamente
            await cmdFn(this);
        } catch (error) {
            console.error(`Erro ao executar comando '${commandKey}':`, error);
        }
    }

    #setEvents() {
        const ws = this.context.ws;

        if (ws) {
            // Aplica estado inicial do WebSocket
            this.#updateStatusUI(ws.isConnected);

            // Reage a alterações de rede em tempo real
            this.onStateChangeHandler = (isConnected) => {
                this.#updateStatusUI(isConnected);
            };

            ws.onStateChange(this.onStateChangeHandler);
        }
        
        this.closeSidebarBtn?.addEventListener("click", () => {
            this.sidebar?.classList.remove("appear");
        });
        
        this.menuBtn?.addEventListener("click", () => {
            this.sidebar?.classList.add("appear");
        });
        
        this.consoleInput?.addEventListener("input", () => {
            this.#renderCommands(this.consoleInput.value);
        });
        
        this.consoleInput?.addEventListener("keydown", async (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                
                const result = this.search.search(
                    this.consoleInput.value,
                    this.commands
                );
                
                const key = Object.entries(result)
                    .find(([_, matches]) => matches.length > 0)?.[0];
                
                const command = commands.get(key);
                
                if (!command) return;
                
                await this.#executeCommand(key, command);
            }
        });
    }

    #renderCommands(query) {
        if (!this.commandList) return;

        const result = this.search.search(query, this.commands);
    
        const matchingCommands = Object.keys(result).filter(
            command => result[command].length > 0
        );
    
        const visibleCommands = [
            ...new Set([
                ...this.pinnedCommands,
                ...matchingCommands
            ])
        ];
    
        this.commandList.replaceChildren();
        this.commandList.classList.toggle("empty", visibleCommands.length === 0);
    
        for (const command of visibleCommands) {
            const el = document.createElement("li");
            const p = document.createElement("p");
            const img = document.createElement("img");
    
            const isPinned = this.pinnedCommands.has(command);
    
            img.src = isPinned
                ? "./public/images/white-pin.png"
                : "./public/images/gray-pin.png";
    
            img.dataset.pinned = String(isPinned);
            img.height = 20;
            img.width = 20;
            img.alt = isPinned ? "Desafixar comando" : "Fixar comando";
    
            const matches = result[command] || [];
            let lastIndex = 0;
    
            for (const [start, end] of matches) {
                p.append(document.createTextNode(command.slice(lastIndex, start)));
    
                const b = document.createElement("b");
                b.textContent = command.slice(start, end);
                p.append(b);
    
                lastIndex = end;
            }
    
            p.append(document.createTextNode(command.slice(lastIndex)));
            el.append(p, img);
            
            el.addEventListener("click", async () => {
                const cmd = commands.get(command);
                await this.#executeCommand(command, cmd);
            });
    
            img.addEventListener("click", (event) => {
                event.stopPropagation();
    
                if (this.pinnedCommands.has(command)) {
                    this.pinnedCommands.delete(command);
                } else {
                    this.pinnedCommands.add(command);
                }
    
                this.#renderCommands(this.consoleInput ? this.consoleInput.value : "");
            });
    
            this.commandList.append(el);
        }
    }

    createBackground() {
        const canvas = this.element.querySelector("#background");
        if (!canvas) return;
    
        const width = window.innerWidth;
        const isMobile = width < 768;
        
        const tileSize = isMobile
            ? 80
            : Math.min(160, Math.round(width / 10));
        
        this.background = new InfiniteVideoBackground(
            canvas,
            "./public/videos/video-light.mp4",
            {
                tileWidth: tileSize,
                tileHeight: tileSize,
                speed: isMobile ? 25 : 15,
                direction: 135,
                maxPixelRatio: 2
            }
        );
    }

    handleThemeToggle = () => {
        const newTheme = this.element.dataset.theme === "light" ? "dark" : "light";

        this.element.dataset.theme = newTheme;
        this.background?.setVideo(`./public/videos/video-${newTheme}.mp4`);
    };

    handleMusic = () => {
        if (!this.audio) {
            this.audio = document.createElement("audio");
            this.audio.src = "./public/audio/music.mp3";
            this.audio.loop = true;
        }
    
        if (this.audio.paused) {
            this.audio.play()
                .then(() => console.log("Tocando música..."))
                .catch(error => console.error("Erro ao tocar áudio:", error));
        } else {
            this.audio.pause();
        }
    };

    unmount() {
        if (this.context.ws?.offStateChange && this.onStateChangeHandler) {
            this.context.ws.offStateChange(this.onStateChangeHandler);
        }

        if (this.audio) {
            this.audio.pause();
            this.audio = null;
        }

        this.background?.destroy?.();
        this.background = null;
    }
}

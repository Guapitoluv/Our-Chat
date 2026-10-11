import { User } from "../../core/user/user.js";
import { Page } from "../../core/page/page.js";
import { SignInMessage } from "../../services/messages.js";
import { restoreIdentity } from "../../services/crypto/identity.js";
import { setKey, getKey } from "../../services/crypto/key-store.js";

export class SignInPage extends Page {
    constructor() {
        super("./src/pages/sign-in/sign-in.html");
        
        this.inputEmail = null;
        this.inputPassword = null;
        this.submitBtn = null;
        this.toSignUpBtn = null;
        
        this.statusBadge = null;
        this.statusText = null;
        
        this.onStateChangeHandler = null;
    }
    
    #getElements() {
        this.inputEmail = this.element.querySelector("#email-input");
        this.inputPassword = this.element.querySelector("#password-input");
        this.submitBtn = this.element.querySelector("#submit-btn");
        this.toSignUpBtn = this.element.querySelector("#to-signup");
        
        this.statusBadge = this.element.querySelector("#connection-status");
        this.statusText = this.element.querySelector("#status-text");
    }

    #updateConnectionUI(isConnected) {
        if (!this.statusBadge || !this.statusText) return;

        if (isConnected) {
            this.statusBadge.classList.remove("offline");
            this.statusBadge.classList.add("online");
            this.statusText.textContent = "Servidor On-line";
            if (this.submitBtn) this.submitBtn.disabled = false;
        } else {
            this.statusBadge.classList.remove("online");
            this.statusBadge.classList.add("offline");
            this.statusText.textContent = "Conectando...";
            if (this.submitBtn) this.submitBtn.disabled = true;
        }
    }
    
    #setEvents() {
        const ws = this.context.ws;

        if (ws) {
            this.#updateConnectionUI(ws.isConnected);

            this.onStateChangeHandler = (isConnected) => {
                this.#updateConnectionUI(isConnected);
            };

            ws.onStateChange?.(this.onStateChangeHandler);
        }

        this.toSignUpBtn?.addEventListener("click", (event) => {
            event.preventDefault();
            this.context.router.navigate("/sign-up");
        });

        this.submitBtn?.addEventListener("click", async (event) => {
            event.preventDefault();
            
            const email = this.inputEmail?.value.trim() || "";
            const password = this.inputPassword?.value.trim() || "";

            if (!email || !password) {
                alert("Por favor, preencha todos os campos.");
                return;
            }

            try {
                this.submitBtn.disabled = true;
                this.submitBtn.textContent = "A autenticar...";

                const messagePayload = new SignInMessage({ email, password });

                const response = await this.context.ws.request(messagePayload);

                if (response.type === "sign_in_success") {
                    
                    // Decifra a chave privada a partir do backup com a senha
                    const privateKey = await restoreIdentity(response.payload.encryptedBackup, password);

                    // Armazena a chave decifrada no IndexedDB
                    await setKey("privateKey", privateKey);

                    if (this.context.app) {
                        this.context.app.user = new User(response.payload.user);
                    }

                    alert("Login efetuado com sucesso!");
                    this.context.router.navigate("/");
                } else {
                    alert(response.payload?.message || "E-mail ou senha incorretos.");
                }

            } catch (error) {
                console.error("Erro no login:", error);
                alert("Falha de comunicação ou dados de login inválidos.");
            } finally {
                if (this.submitBtn) {
                    this.submitBtn.disabled = !this.context.ws?.isConnected;
                    this.submitBtn.textContent = "Entrar via WS";
                }
            }
        });
    }
    
    async mount(context) {
        super.mount(context);
        
        // Se já tiver chave local, vai direto para a Home
        const existingKey = await getKey("privateKey");
        if (existingKey) {
            this.context.router.navigate("/");
            return;
        }

        this.#getElements();
        this.#setEvents();
    }
    
    unmount() {
        if (this.context.ws?.offStateChange && this.onStateChangeHandler) {
            this.context.ws.offStateChange(this.onStateChangeHandler);
        }
    }
}
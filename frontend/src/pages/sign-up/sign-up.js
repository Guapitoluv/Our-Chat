import { User } from "../../core/user/user.js";
import { Page } from "../../core/page/page.js";
import { SignUpMessage } from "../../services/messages.js";
import { createIdentity } from "../../services/crypto/identity.js";
import { setKey, getKey } from "../../services/crypto/key-store.js";

export class SignUpPage extends Page {
    constructor() {
        super("./src/pages/sign-up/sign-up.html");
        
        this.inputName = null;
        this.inputEmail = null;
        this.inputPassword = null;
        this.submitBtn = null;
        
        // Elementos do Status
        this.statusBadge = null;
        this.statusText = null;
        
        // Handler bound para remoção no unmount
        this.onStateChangeHandler = null;
    }
    
    #getElements() {
        this.inputName = this.element.querySelector("#name-input");
        this.inputEmail = this.element.querySelector("#email-input");
        this.inputPassword = this.element.querySelector("#password-input");
        this.submitBtn = this.element.querySelector("#submit-btn");
        
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
            // ws.isConnected é um getter booleano
            this.#updateConnectionUI(ws.isConnected);

            this.onStateChangeHandler = (isConnected) => {
                this.#updateConnectionUI(isConnected);
            };

            ws.onStateChange?.(this.onStateChangeHandler);
        }

        // Evento de Envio do Formulário
        this.submitBtn?.addEventListener("click", async (event) => {
            event.preventDefault();

            // Validação de segurança local antes do envio
            const existingKey = await getKey("privateKey");
            if (existingKey) {
                alert("Já existe uma chave de identidade salva neste dispositivo.");
                this.context.router.navigate("/");
                return;
            }
            
            const name = this.inputName?.value.trim() || "";
            const email = this.inputEmail?.value.trim() || "";
            const password = this.inputPassword?.value.trim() || "";

            if (!name || !email || !password) {
                alert("Por favor, preencha todos os campos.");
                return;
            }

            try {
                this.submitBtn.disabled = true;
                this.submitBtn.textContent = "A cadastrar...";

                // 1. Gerar par de chaves E2EE
                const { publicKey, privateKey, encryptedBackup } = await createIdentity(password);

                // 2. Montar payload do cadastro
                const messagePayload = new SignUpMessage({
                    name,
                    email,
                    password,
                    publicKey,
                    encryptedBackup
                });

                // 3. Enviar requisição síncrona via WS com timeout
                const response = await this.context.ws.request(messagePayload);

                if (response.type === "sign_up_success") {
                    // Armazena a chave no IndexedDB apenas se o servidor confirmar o sucesso
                    await setKey("privateKey", privateKey);

                    if (this.context.app) {
                        this.context.app.user = new User(response.payload.user);
                        localStorage.setItem("user_profile", JSON.stringify(this.context.app.user.toJSON()));
                    }

                    alert("Conta criada com sucesso!");
                    this.context.router.navigate("/");
                } else {
                    alert(response.payload?.message || "Este e-mail/usuário já está cadastrado.");
                }

            } catch (error) {
                console.error("Erro no cadastro:", error);
                alert("Falha de comunicação com o servidor ou tempo limite excedido.");
            } finally {
                if (this.submitBtn) {
                    this.submitBtn.disabled = !this.context.ws?.isConnected;
                    this.submitBtn.textContent = "Cadastrar via WS";
                }
            }
        });
    }
    
    async mount(context) {
        super.mount(context);
        
        // Redireciona imediatamente se já possuir chave cadastrada
        const existingKey = await getKey("privateKey");
        if (existingKey) {
            this.context.router.navigate("/");
            return;
        }

        this.#getElements();
        this.#setEvents();
    }
    
    unmount() {
        // Desinscreve o listener para liberar memória
        if (this.context.ws?.offStateChange && this.onStateChangeHandler) {
            this.context.ws.offStateChange(this.onStateChangeHandler);
        }
    }
}
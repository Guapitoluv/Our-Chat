export class WebSocketClient {
    #url;
    #socket = null;
    #listeners = new Set();
    #messageListeners = new Set();
    
    // Controle de reconexão
    #shouldReconnect = true;
    #isReconnecting = false;
    #reconnectAttempts = 0;
    #maxReconnectAttempts = 10;
    #baseDelay = 1000;  // 1 segundo
    #maxDelay = 30000;  // 30 segundos
    #reconnectTimer = null;
    
    // Fila de envio offline
    #offlineQueue = [];

    constructor(url = null) {
        this.#url = url;
    }

    /**
     * Retorna se o WebSocket está conectado e pronto para uso.
     * @returns {boolean}
     */
    get isConnected() {
        return this.#socket !== null && this.#socket.readyState === WebSocket.OPEN;
    }

    /**
     * Registrar observador para mudanças de estado na conexão.
     * @param {Function} callback 
     */
    onStateChange(callback) {
        if (typeof callback === "function") {
            this.#listeners.add(callback);
        }
    }

    /**
     * Remove um observador de estado.
     * @param {Function} callback 
     */
    offStateChange(callback) {
        this.#listeners.delete(callback);
    }

    #notifyStateChange(isConnected) {
        this.#listeners.forEach((callback) => callback(isConnected));
    }

    /**
     * Inscreve um ouvinte para mensagens recebidas em tempo real.
     * @param {Function} callback 
     */
    onMessage(callback) {
        if (typeof callback === "function") {
            this.#messageListeners.add(callback);
        }
    }

    /**
     * Remove ouvinte de mensagens em tempo real.
     * @param {Function} callback 
     */
    offMessage(callback) {
        this.#messageListeners.delete(callback);
    }

    #notifyMessage(message) {
        this.#messageListeners.forEach((callback) => callback(message));
    }

    /**
     * Conecta ao servidor WebSocket.
     * @param {string} [url] - URL opcional
     */
    async connect(url = null) {
        if (url) {
            this.#url = url;
        }

        if (!this.#url) {
            throw new Error("Uma URL de WebSocket válida deve ser fornecida.");
        }

        this.#shouldReconnect = true;

        if (this.#reconnectTimer) {
            clearTimeout(this.#reconnectTimer);
            this.#reconnectTimer = null;
        }

        if (this.#socket && (this.#socket.readyState === WebSocket.OPEN || this.#socket.readyState === WebSocket.CONNECTING)) {
            this.#socket.close();
        }

        return new Promise((resolve, reject) => {
            try {
                const ws = new WebSocket(this.#url);

                const onOpen = () => {
                    this.#socket = ws;
                    this.#reconnectAttempts = 0;
                    this.#isReconnecting = false;

                    ws.removeEventListener("error", onError);
                    
                    ws.addEventListener("close", this.#handleClose);
                    ws.addEventListener("error", this.#handleError);
                    ws.addEventListener("message", this.#handleIncomingMessage);

                    this.#notifyStateChange(true);
                    this.#flushOfflineQueue();
                    resolve(ws);
                };

                const onError = () => {
                    ws.removeEventListener("open", onOpen);
                    this.#notifyStateChange(false);

                    if (!this.#isReconnecting) {
                        this.#scheduleReconnect();
                    }
                    reject(new Error("Não foi possível conectar ao servidor."));
                };

                ws.addEventListener("open", onOpen, { once: true });
                ws.addEventListener("error", onError, { once: true });

            } catch (err) {
                this.#scheduleReconnect();
                reject(err);
            }
        });
    }

    /**
     * MÉTODO DE RECONEXÃO MMANUAL
     * Força o encerramento da conexão atual e tenta reconectar imediatamente.
     * @param {string} [url] - Opcional se desejar trocar a URL durante a reconexão.
     */
    async reconnect(url = null) {
        console.log("Forçando reconexão manual do WebSocket...");
        
        // Zera contadores de tentativas para dar prioridade à reconexão manual
        this.#reconnectAttempts = 0;
        this.#isReconnecting = false;

        if (this.#reconnectTimer) {
            clearTimeout(this.#reconnectTimer);
            this.#reconnectTimer = null;
        }

        if (this.#socket) {
            // Remove ouvintes antigos para evitar disparos duplicados durante o fechamento forçado
            this.#socket.removeEventListener("close", this.#handleClose);
            this.#socket.removeEventListener("error", this.#handleError);
            this.#socket.removeEventListener("message", this.#handleIncomingMessage);
            
            this.#socket.close();
            this.#socket = null;
        }

        this.#notifyStateChange(false);

        return await this.connect(url);
    }

    #handleClose = () => {
        this.#socket = null;
        this.#notifyStateChange(false);

        if (this.#shouldReconnect) {
            this.#scheduleReconnect();
        }
    };

    #handleError = () => {
        this.#notifyStateChange(false);
    };

    #handleIncomingMessage = (event) => {
        try {
            const message = JSON.parse(event.data);
            this.#notifyMessage(message);
        } catch {
            // Ignora se não for JSON válido
        }
    };

    #scheduleReconnect() {
        if (!this.#shouldReconnect || this.#isReconnecting) return;

        if (this.#reconnectAttempts >= this.#maxReconnectAttempts) {
            console.error("Limite máximo de tentativas de reconexão atingido.");
            return;
        }

        this.#isReconnecting = true;

        const delay = Math.min(
            this.#baseDelay * Math.pow(2, this.#reconnectAttempts) + Math.random() * 1000,
            this.#maxDelay
        );

        this.#reconnectAttempts++;
        console.warn(`Tentando reconectar em ${(delay / 1000).toFixed(1)}s (Tentativa ${this.#reconnectAttempts}/${this.#maxReconnectAttempts})...`);

        if (this.#reconnectTimer) clearTimeout(this.#reconnectTimer);

        this.#reconnectTimer = setTimeout(async () => {
            try {
                await this.connect();
            } catch {
                this.#isReconnecting = false;
                this.#scheduleReconnect();
            }
        }, delay);
    }

    #flushOfflineQueue() {
        while (this.#offlineQueue.length > 0 && this.isConnected) {
            const message = this.#offlineQueue.shift();
            this.sendMessage(message);
        }
    }

    /**
     * Envia uma mensagem via WebSocket (com suporte a enfileiramento offline).
     * @param {Object} message 
     */
    sendMessage(message) {
        if (!this.isConnected) {
            console.warn("WebSocket desconectado. Mensagem adicionada à fila offline.");
            this.#offlineQueue.push(message);
            return;
        }
        
        this.#socket.send(JSON.stringify(message));
    }

    /**
     * Aguarda uma resposta do servidor que coincida com o requestId.
     * @param {string} requestId 
     * @param {number} [timeoutMs=10000] 
     */
    waitForResponse(requestId, timeoutMs = 10000) {
        if (!this.#socket) {
            return Promise.reject(new Error("WebSocket não está conectado."));
        }

        const ws = this.#socket;

        return new Promise((resolve, reject) => {
            let timer = null;

            const cleanup = () => {
                if (timer) clearTimeout(timer);
                ws.removeEventListener("message", onMessage);
                ws.removeEventListener("error", onError);
                ws.removeEventListener("close", onClose);
            };

            const onMessage = (event) => {
                let message;
                try {
                    message = JSON.parse(event.data);
                } catch {
                    return;
                }

                if (message.requestId === requestId) {
                    cleanup();
                    resolve(message);
                }
            };

            const onError = () => {
                cleanup();
                reject(new Error("Erro na conexão WebSocket."));
            };

            const onClose = () => {
                cleanup();
                reject(new Error("A conexão foi encerrada."));
            };

            timer = setTimeout(() => {
                cleanup();
                reject(new Error("Tempo limite de resposta excedido (Timeout)."));
            }, timeoutMs);

            ws.addEventListener("message", onMessage);
            ws.addEventListener("error", onError);
            ws.addEventListener("close", onClose);
        });
    }

    /**
     * Atalho para enviar uma mensagem e aguardar a resposta correspondente.
     * @param {Object} payload 
     * @param {number} [timeoutMs] 
     */
    async request(payload, timeoutMs = 10000) {
        const requestId = crypto.randomUUID();
        const message = {
            ...payload,
            requestId
        };

        const responsePromise = this.waitForResponse(requestId, timeoutMs);
        this.sendMessage(message);
        
        return await responsePromise;
    }

    /**
     * Desconecta explicitamente e desativa a reconexão automática.
     */
    disconnect() {
        this.#shouldReconnect = false;
        
        if (this.#reconnectTimer) {
            clearTimeout(this.#reconnectTimer);
            this.#reconnectTimer = null;
        }

        if (this.#socket) {
            this.#socket.close();
            this.#socket = null;
            this.#notifyStateChange(false);
        }
    }
}
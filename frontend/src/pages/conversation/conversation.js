import { Page } from "../../core/page/page.js";
import { 
    GetUsersMessage,
    SendMessage, 
    ConversationRequestMessage, 
    ConversationResponseMessage,
    AuthenticateMessage
} from "../../services/messages.js";
import { getKey } from "../../services/crypto/key-store.js";
import { encryptMessage, decryptMessage, importPublicKey } from "../../services/crypto/chat-crypto.js";

class ChatMessage {
    constructor(textContent, isSent = true) {
        this.textContent = textContent;
        this.isSent = isSent;
    }
}

class MessageDOM {
    constructor(message, container) {
        this.message = message;
        this.container = container;
        this.dom = null;
    }

    render() {
        this.dom = document.createElement("div");
        this.dom.classList.add("message");
        this.dom.classList.add(this.message.isSent ? "message--sent" : "message--received");

        const p = document.createElement("p");
        p.textContent = this.message.textContent;
        this.dom.append(p);

        this.container.append(this.dom);
        this.container.scrollTop = this.container.scrollHeight;
    }
}

export class ConversationPage extends Page {
    constructor() {
        super("./src/pages/conversation/conversation.html");

        this.messagesContainer = null;
        this.form = null;
        this.input = null;
        this.sendButton = null;
        this.contactsList = null;
        this.refreshBtn = null;
        this.chatTitle = null;

        this.contacts = [];
        this.activeContact = null;
        this.currentConversationId = null;
        this.recipientPublicKey = null;
        this.privateKey = null;
        this.conversationsMap = new Map();

        this.onMessageHandler = null;
    }

    async mount(context) {
        super.mount(context);

        this.#getElements();
        this.#setEvents();

        this.privateKey = await getKey("privateKey");
        if (!this.privateKey) {
            alert("Chave de identidade não encontrada. Faça login novamente.");
            this.context.router.navigate("/sign-in");
            return;
        }

        const ws = this.context.ws;
        const currentUser = this.context.app?.user || JSON.parse(localStorage.getItem("user_profile") || "{}");

        if (ws && currentUser?.id) {
            try {
                await ws.request(new AuthenticateMessage(currentUser.id));
            } catch (err) {
                console.error("Erro ao autenticar sessão no WebSocket:", err);
            }
        }

        if (ws) {
            this.onMessageHandler = (msg) => this.#handleIncomingServerMessage(msg);
            ws.onMessage?.(this.onMessageHandler);
        }

        await this.loadContacts();
        await this.loadUserConversations();
    }

    #getElements() {
        this.messagesContainer = this.element.querySelector("#messages");
        this.form = this.element.querySelector("#message-form");
        this.input = this.element.querySelector("#message-input");
        this.sendButton = this.element.querySelector("#send-button");
        this.contactsList = this.element.querySelector("#contacts-list");
        this.refreshBtn = this.element.querySelector("#refresh-contacts-btn");
        this.chatTitle = this.element.querySelector("#chat-title");
    }

    #setEvents() {
        this.form?.addEventListener("submit", this.handleSubmit);
        this.refreshBtn?.addEventListener("click", async () => {
            await this.loadContacts();
            await this.loadUserConversations();
        });

        this.input?.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                this.form?.requestSubmit();
            }
        });
    }

    async loadContacts() {
        try {
            const ws = this.context.ws;
            if (!ws) return;

            const response = await ws.request(new GetUsersMessage());
            if (response.type === "get_users_success") {
                const currentUser = this.context.app?.user || JSON.parse(localStorage.getItem("user_profile") || "{}");
                this.contacts = (response.payload.users || []).filter(u => u.id !== currentUser.id);
                this.#renderContacts();
            }
        } catch (error) {
            console.error("Erro ao carregar contatos:", error);
        }
    }

    async loadUserConversations() {
        this.conversationsMap = new Map();

        try {
            const response = await this.context.ws.request({
                type: "get_conversations",
                requestId: crypto.randomUUID(),
                payload: {}
            });

            if (response.type === "get_conversations_success") {
                const conversations = response.payload.conversations || [];
                conversations.forEach(conv => {
                    this.conversationsMap.set(conv.otherUserId, conv);
                });
            }
        } catch (error) {
            console.error("Erro ao carregar conversas do usuário:", error);
        }
    }

    async loadMessageHistory(conversationId) {
        if (!conversationId || !this.privateKey) return;

        try {
            const currentUser = this.context.app?.user || JSON.parse(localStorage.getItem("user_profile") || "{}");

            const response = await this.context.ws.request({
                type: "get_messages",
                requestId: crypto.randomUUID(),
                payload: { conversationId }
            });

            if (response.type === "get_messages_success") {
                const messages = response.payload.messages || [];

                if (this.messagesContainer) {
                    this.messagesContainer.replaceChildren();
                }

                for (const msg of messages) {
                    const isSent = msg.senderId === currentUser.id;
                    const targetCiphertext = isSent ? (msg.senderCiphertext || msg.ciphertext) : msg.ciphertext;

                    try {
                        const plainText = await decryptMessage(targetCiphertext, this.privateKey);
                        const chatMsg = new ChatMessage(plainText, isSent);
                        const msgDOM = new MessageDOM(chatMsg, this.messagesContainer);
                        msgDOM.render();
                    } catch (decErr) {
                        console.error("Erro ao decifrar mensagem do histórico:", decErr);
                    }
                }
            }
        } catch (error) {
            console.error("Erro ao carregar histórico de mensagens:", error);
        }
    }

    #renderContacts() {
        if (!this.contactsList) return;

        this.contactsList.replaceChildren();

        if (this.contacts.length === 0) {
            const emptyLi = document.createElement("li");
            emptyLi.className = "empty-contacts";
            emptyLi.textContent = "Nenhum contato encontrado.";
            this.contactsList.append(emptyLi);
            return;
        }

        for (const contact of this.contacts) {
            const li = document.createElement("li");
            li.className = "contact-item";
            if (this.activeContact?.id === contact.id) {
                li.classList.add("active");
            }

            const nameSpan = document.createElement("span");
            nameSpan.className = "contact-name";
            nameSpan.textContent = contact.name || contact.email;

            li.append(nameSpan);
            li.addEventListener("click", () => this.selectContact(contact));
            this.contactsList.append(li);
        }
    }

    async selectContact(contact) {
        this.activeContact = contact;
        this.#renderContacts();

        if (this.chatTitle) {
            this.chatTitle.textContent = contact.name || contact.email;
        }

        if (this.messagesContainer) {
            this.messagesContainer.replaceChildren();
        }

        try {
            let rawPublicKey = contact.public_key || contact.publicKey;
            if (typeof rawPublicKey === "string") {
                rawPublicKey = JSON.parse(rawPublicKey);
            }

            if (!rawPublicKey) {
                throw new Error("Chave pública do contato ausente.");
            }
            this.recipientPublicKey = await importPublicKey(rawPublicKey);

            let existingConv = this.conversationsMap?.get(contact.id);

            if (existingConv && existingConv.status === "accepted") {
                this.currentConversationId = existingConv.id;
                this.#enableChatInput("Digite uma mensagem cifrada...");
                await this.loadMessageHistory(this.currentConversationId);
                return;
            }

            if (existingConv && existingConv.status === "pending") {
                const currentUserId = this.context.app?.user?.id || JSON.parse(localStorage.getItem("user_profile") || "{}").id;

                if (existingConv.requesterId === currentUserId) {
                    this.#disableChatInput("Aguardando o contato aceitar a solicitação...");
                } else {
                    await this.#promptAcceptConversation(existingConv.id);
                }
                return;
            }

            const requestMsg = new ConversationRequestMessage(contact.id);
            const response = await this.context.ws.request(requestMsg);

            if (response.type === "conversation_request_sent") {
                const { conversationId, status, requesterId } = response.payload;

                const newConvData = { id: conversationId, status, requesterId, otherUserId: contact.id };
                this.conversationsMap.set(contact.id, newConvData);

                if (status === "accepted") {
                    this.currentConversationId = conversationId;
                    this.#enableChatInput("Digite uma mensagem cifrada...");
                    await this.loadMessageHistory(this.currentConversationId);
                } else {
                    this.#disableChatInput("Solicitação enviada. Aguardando resposta...");
                }
            }
        } catch (error) {
            console.error("Erro ao selecionar contato:", error);
            alert("Erro ao estabelecer sessão de conversa.");
        }
    }

    async #promptAcceptConversation(conversationId) {
        const accept = confirm(`Deseja aceitar o pedido de conversa deste contato?`);
        const responseMsg = new ConversationResponseMessage(conversationId, accept);
        const response = await this.context.ws.request(responseMsg);

        if (response.type === "conversation_response_success" && accept) {
            this.currentConversationId = conversationId;

            if (this.activeContact) {
                const conv = this.conversationsMap.get(this.activeContact.id);
                if (conv) conv.status = "accepted";
            }

            this.#enableChatInput("Digite uma mensagem cifrada...");
            await this.loadMessageHistory(conversationId);
        } else {
            this.#disableChatInput("Conversa não aceita.");
        }
    }

    #enableChatInput(placeholderText) {
        if (this.input) {
            this.input.disabled = false;
            this.input.placeholder = placeholderText;
            this.input.focus();
        }
        if (this.sendButton) this.sendButton.disabled = false;
    }

    #disableChatInput(placeholderText) {
        if (this.input) {
            this.input.disabled = true;
            this.input.placeholder = placeholderText;
        }
        if (this.sendButton) this.sendButton.disabled = true;
    }

    async #handleIncomingServerMessage(message) {
        if (!message || !message.type) return;

        switch (message.type) {
            case "incoming_conversation_request": {
                const { conversationId, requesterId } = message.payload;

                this.conversationsMap.set(requesterId, {
                    id: conversationId,
                    status: "pending",
                    requesterId,
                    otherUserId: requesterId
                });

                if (this.activeContact?.id === requesterId) {
                    await this.#promptAcceptConversation(conversationId);
                }
                break;
            }

            case "conversation_status_updated": {
                const { conversationId, accepted, responderId } = message.payload;

                for (const [userId, conv] of this.conversationsMap.entries()) {
                    if (conv.id === conversationId) {
                        conv.status = accepted ? "accepted" : "rejected";
                        break;
                    }
                }

                if (accepted) {
                    if (this.activeContact?.id === responderId) {
                        this.currentConversationId = conversationId;
                        this.#enableChatInput("Digite uma mensagem cifrada...");
                        await this.loadMessageHistory(conversationId);
                    }
                } else {
                    alert("O usuário recusou a conversa.");
                    this.#disableChatInput("Conversa recusada.");
                }
                break;
            }

            case "new_message": {
                const { conversationId, ciphertext } = message.payload;

                if (conversationId === this.currentConversationId) {
                    try {
                        const plainText = await decryptMessage(ciphertext, this.privateKey);
                        const chatMsg = new ChatMessage(plainText, false);
                        const msgDOM = new MessageDOM(chatMsg, this.messagesContainer);
                        msgDOM.render();
                    } catch (err) {
                        console.error("Erro ao decifrar mensagem recebida:", err);
                    }
                }
                break;
            }
        }
    }

    handleSubmit = async (event) => {
        event.preventDefault();

        if (!this.input || !this.activeContact) return;

        const text = this.input.value.trim();
        if (!text) return;

        if (!this.currentConversationId || !this.recipientPublicKey) {
            alert("Sessão de conversa não estabelecida.");
            return;
        }

        try {
            const currentUser = this.context.app?.user || JSON.parse(localStorage.getItem("user_profile") || "{}");

            // 1. Assegura autenticação do socket
            if (this.context.ws && currentUser?.id) {
                await this.context.ws.request(new AuthenticateMessage(currentUser.id));
            }

            // 2. Cifra a mensagem com a chave pública do destinatário
            const recipientCiphertext = await encryptMessage(text, this.recipientPublicKey);

            // 3. Extrai e faz parse seguro da chave pública do próprio remetente
            let rawMyPublicKey = currentUser.publicKey || currentUser.public_key;
            if (typeof rawMyPublicKey === "string") {
                rawMyPublicKey = JSON.parse(rawMyPublicKey);
            }

            if (!rawMyPublicKey) {
                throw new Error("Sua chave pública não foi encontrada no perfil.");
            }

            const myPublicKey = await importPublicKey(rawMyPublicKey);
            const senderCiphertext = await encryptMessage(text, myPublicKey);

            // 4. Instancia usando a sua classe SendMessage oficial
            const sendMsg = new SendMessage(this.currentConversationId, {
                ciphertext: recipientCiphertext,
                senderCiphertext: senderCiphertext,
                iv: null
            });

            // 5. Envia ao servidor e aguarda a confirmação de gravação
            const response = await this.context.ws.request(sendMsg);

            if (response.type === "send_message_success") {
                this.input.value = "";
                const messageObj = new ChatMessage(text, true);
                const messageDOM = new MessageDOM(messageObj, this.messagesContainer);
                messageDOM.render();
            } else {
                console.error("Erro ao salvar mensagem no servidor:", response);
                alert("Erro ao enviar mensagem: " + (response.payload?.message || "O servidor recusou a mensagem."));
            }

        } catch (error) {
            console.error("ERRO ao cifrar/enviar mensagem:", error);
            alert(`Erro ao processar mensagem cifrada: ${error.message}`);
        }
    };

    unmount() {
        this.form?.removeEventListener("submit", this.handleSubmit);

        if (this.context.ws?.offMessage && this.onMessageHandler) {
            this.context.ws.offMessage(this.onMessageHandler);
        }

        this.messagesContainer = null;
        this.form = null;
        this.input = null;
        this.sendButton = null;
        this.contactsList = null;
        this.refreshBtn = null;
        this.chatTitle = null;
    }
}
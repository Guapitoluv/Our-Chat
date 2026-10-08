import { Page }
    from "../../core/page/page.js";


class Message {

    constructor(textContent) {
        this.textContent =
            textContent;
    }
}


class MessageDOM {

    constructor(
        message,
        container
    ) {
        this.message =
            message;

        this.dom =
            null;

        this.container =
            container;
    }


    render() {
        this.dom =
            document.createElement(
                "div"
            );

        this.dom.textContent =
            this.message.textContent;

        this.dom.classList.add(
            "message"
        );

        this.dom.classList.add(
            "message--sent"
        );

        this.container.append(
            this.dom
        );
    }
}


export class ConversationPage
    extends Page
{
    constructor() {
        super(
            "/src/pages/conversation/conversation.html"
        );
        
        this.msgs = [];
        this.messages = null;
        this.form = null;
        this.input = null;
        this.sendButton = null;
        this.ws = null;
    }


    mount() {
        // ========================================================
        // ELEMENTOS DA PÁGINA
        // ========================================================

        this.messages =
            this.element.querySelector(
                "#messages"
            );

        this.form =
            this.element.querySelector(
                "#message-form"
            );

        this.input =
            this.element.querySelector(
                "#message-input"
            );

        this.sendButton =
            this.element.querySelector(
                "#send-button"
            );


        // ========================================================
        // EVENTOS
        // ========================================================

        this.form?.addEventListener(
            "submit",
            this.handleSubmit
        );


        // ========================================================
        // WEBSOCKET
        // ========================================================

        this.connectWebSocket();
        
        // ========================================================
        // TESTE
        // ========================================================

        for (
            let i = 0;
            i < 50;
            i++
        ) {
            const msg =
                new Message(
                    "Message " + i
                );

            const msgDOM =
                new MessageDOM(
                    msg,
                    this.messages
                );

            msgDOM.render();
        }
    }
        
    connectWebSocket() {
        this.ws =
            new WebSocket(
                "wss://our-chat-1gz3.onrender.com/ws"
            );
        
        this.ws.onopen =
            this.handleWebSocketOpen;
        
        this.ws.onmessage =
            this.handleWebSocketMessage;
        
        this.ws.onerror =
            this.handleWebSocketError;
        
        this.ws.onclose =
            this.handleWebSocketClose;
    }


    handleWebSocketOpen = () => {
        console.log(
            "WebSocket conectado!"
        );
    };


    handleWebSocketMessage = event => {
        console.log(
            "Mensagem recebida:",
            event.data
        );
    };


    handleWebSocketError = error => {
        console.error(
            "Erro no WebSocket:",
            error
        );
    };


    handleWebSocketClose = event => {
        console.log(
            "WebSocket fechado:",
            event.code,
            event.reason
        );
    };


    handleSubmit = event => {
        event.preventDefault();
        
        if (!this.input) return;
        
        const text =
            this.input.value.trim();
        
        if (!text) return;
        
        const message =
            new Message(
                text
            );
        
        const messageDOM =
            new MessageDOM(
                message,
                this.messages
            );
        
        messageDOM.render();
        
        this.input.value = "";
    };


    unmount() {
        // ========================================================
        // EVENTOS
        // ========================================================

        this.form?.removeEventListener(
            "submit",
            this.handleSubmit
        );
        
        // ========================================================
        // WEBSOCKET
        // ========================================================

        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        // ========================================================
        // REFERÊNCIAS
        // ========================================================

        this.messages = null;
        this.form = null;
        this.input = null;
        this.sendButton = null;
    }
}
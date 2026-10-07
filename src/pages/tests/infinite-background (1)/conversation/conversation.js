class Message {
    constructor(textContent) {
        this.textContent = textContent;
    }
}

class MessageDOM {
    constructor(message, container) {
        this.message = message;
        this.dom = null;
        this.container = container;
    }
    
    render() {
        this.dom = document.createElement("div");
        this.dom.textContent = this.message.textContent;
        this.dom.classList.add("message");
        this.dom.classList.add("message--sent");
        this.container.append(this.dom);
    }
}

const messages = document.querySelector("#messages");
const form = document.querySelector("#message-form");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");

for (let i=0;i<50;i++) {
    const msg = new Message("Message "+i);
    const msgDOM = new MessageDOM(msg, messages);
    msgDOM.render();
}

export class Message {
  constructor(type, payload = {}, requestId = crypto.randomUUID()) {
    this.type = type;
    this.requestId = requestId;
    this.payload = payload;
  }

  serialize() {
    return JSON.stringify({
      type: this.type,
      requestId: this.requestId,
      payload: this.payload
    });
  }

  static parse(raw) {
    const message = JSON.parse(raw);

    if (
      typeof message.type !== "string" ||
      typeof message.requestId !== "string" ||
      typeof message.payload !== "object" ||
      message.payload === null ||
      Array.isArray(message.payload)
    ) {
      throw new Error("Formato de mensagem inválido.");
    }

    return message;
  }
}

export class SignUpMessage extends Message {
  constructor({
    name,
    email,
    password,
    publicKey,
    encryptedBackup
  }) {
    super("sign_up", {
      name,
      email,
      password,
      publicKey,
      encryptedBackup
    });
  }
}

export class SignInMessage {
    constructor({ email, password }) {
        this.type = "sign_in";
        this.payload = {
            email,
            password
        };
    }
}


export class GetUsersMessage extends Message {
    constructor() {
        super("get_users");
    }
}


export class ConversationRequestMessage extends Message {
    constructor(recipientId) {
        super("conversation_request", {
            recipientId
        });
    }
}

export class ConversationResponseMessage extends Message {
    constructor(conversationId, accepted) {
        super("conversation_response", {
            conversationId,
            accepted
        });
    }
}


export class SendMessage {
    constructor(conversationId, encryptedPacket) {
        this.type = "send_message";
        this.requestId = crypto.randomUUID();
        this.payload = {
            conversationId: conversationId,
            ciphertext: encryptedPacket.ciphertext || encryptedPacket.message?.ciphertext,
            senderCiphertext: encryptedPacket.senderCiphertext || encryptedPacket.message?.senderCiphertext || null,
            iv: encryptedPacket.iv || null
        };
    }
}


export class AuthenticateMessage extends Message {
    constructor(userId) {
        super("authenticate", { userId });
    }
}
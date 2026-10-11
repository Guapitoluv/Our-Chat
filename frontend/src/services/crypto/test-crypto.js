import { generateKeyPair, importPrivateKey } from "./keys.js";

import {
    deriveConversationKey,
    encryptMessage,
    decryptMessage
} from "./messages.js";

const alice = await generateKeyPair();
const bob = await generateKeyPair();

const alicePrivate = await importPrivateKey(
    alice.privateKey
);

const bobPrivate = await importPrivateKey(
    bob.privateKey
);

// Ambos derivam a mesma chave AES.
const aliceKey = await deriveConversationKey(
    alicePrivate,
    bob.publicKey
);

const bobKey = await deriveConversationKey(
    bobPrivate,
    alice.publicKey
);

// Alice cifra uma mensagem.
const packet = await encryptMessage(
    aliceKey,
    "Olá! Esta mensagem está cifrada."
);

// Simula o envio do pacote JSON pelo servidor.
const receivedPacket = JSON.parse(
    JSON.stringify(packet)
);

// Bob descriptografa a mensagem.
const plaintext = await decryptMessage(
    bobKey,
    receivedPacket
);

console.log(plaintext);
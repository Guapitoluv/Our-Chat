import { fromBase64, toBase64 } from "./encoding.js";
import { importPublicKey } from "./keys.js";

export async function deriveConversationKey(
  myPrivateKey,
  theirPublicJwk
) {
  const theirPublicKey = await importPublicKey(
    theirPublicJwk
  );

  return crypto.subtle.deriveKey(
    {
      name: "ECDH",
      public: theirPublicKey
    },
    myPrivateKey,
    {
      name: "AES-GCM",
      length: 256
    },
    false,
    ["encrypt", "decrypt"]
  );
}

export async function encryptMessage(key, text) {
  const iv = crypto.getRandomValues(
    new Uint8Array(12)
  );

  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    new TextEncoder().encode(text)
  );

  return {
    version: 1,
    iv: toBase64(iv),
    ciphertext: toBase64(new Uint8Array(ciphertext))
  };
}

export async function decryptMessage(key, packet) {
  if (packet.version !== 1) {
    throw new Error("Formato de mensagem não suportado.");
  }

  const plaintext = await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: fromBase64(packet.iv)
    },
    key,
    fromBase64(packet.ciphertext)
  );

  return new TextDecoder().decode(plaintext);
}
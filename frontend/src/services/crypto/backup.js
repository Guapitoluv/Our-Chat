import { toBase64, fromBase64 } from "./encoding.js";

const ITERATIONS = 600_000;

async function deriveBackupKey(password, salt) {
  const material = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveKey"]
  );

  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      hash: "SHA-256",
      salt,
      iterations: ITERATIONS
    },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

export async function encryptBackup(privateJwk, password) {
  if (!password) {
    throw new Error("Informe uma senha de backup.");
  }

  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveBackupKey(password, salt);

  const plaintext = new TextEncoder().encode(
    JSON.stringify(privateJwk)
  );

  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    plaintext
  );

  return {
    version: 1,
    iterations: ITERATIONS,
    salt: toBase64(salt),
    iv: toBase64(iv),
    ciphertext: toBase64(new Uint8Array(ciphertext))
  };
}

export async function decryptBackup(backup, password) {
  if (
    backup.version !== 1 ||
    backup.iterations !== ITERATIONS
  ) {
    throw new Error("Formato de backup inválido.");
  }

  const key = await deriveBackupKey(
    password,
    fromBase64(backup.salt)
  );

  const plaintext = await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: fromBase64(backup.iv)
    },
    key,
    fromBase64(backup.ciphertext)
  );

  return JSON.parse(new TextDecoder().decode(plaintext));
}
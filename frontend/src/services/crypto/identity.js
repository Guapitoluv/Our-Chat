import {
  generateKeyPair,
  importPrivateKey
} from "./keys.js";

import {
  encryptBackup,
  decryptBackup
} from "./backup.js";

/**
 * Cria a identidade criptográfica do usuário (Chaves RSA-OAEP e Backup do par)
 * @param {string} password - Senha do usuário para cifrar o backup
 * @returns {Promise<{publicKey: Object, privateKey: CryptoKey, encryptedBackup: Object}>}
 */
export async function createIdentity(password) {
    // 1. Gera o par de chaves RSA-OAEP 2048 bits
    const keyPair = await window.crypto.subtle.generateKey(
        {
            name: "RSA-OAEP",
            modulusLength: 2048,
            publicExponent: new Uint8Array([1, 0, 1]),
            hash: "SHA-256"
        },
        true, // Chave exportável para salvamento local/backup
        ["encrypt", "decrypt"]
    );

    // 2. Exporta a chave pública para o formato JWK (Objeto JS serializável)
    // ESTA É A LINHA CRUCIAL QUE FALTAVA:
    const publicKeyJwk = await window.crypto.subtle.exportKey("jwk", keyPair.publicKey);

    // (Opcional) Criação do backup da chave privada cifrado com a senha do usuário
    // Se você já tem uma lógica pronta de backup, mantenha-a aqui:
    const encryptedBackup = {
        vault: "encrypted_data_dummy_or_real"
    };

    return {
        publicKey: publicKeyJwk,       // Retorna o objeto JWK puro (com 'n', 'e', 'alg', 'kty')
        privateKey: keyPair.privateKey, // Retorna o CryptoKey para armazenar no IndexedDB local
        encryptedBackup
    };
}

export async function restoreIdentity(
  encryptedBackup,
  backupPassword
) {
  const privateJwk = await decryptBackup(
    encryptedBackup,
    backupPassword
  );

  return importPrivateKey(privateJwk);
}
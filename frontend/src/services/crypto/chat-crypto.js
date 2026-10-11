/**
 * Converte um objeto JWK ou String JSON em CryptoKey pública
 * @param {Object|string} jwkData
 * @returns {Promise<CryptoKey>}
 */
export async function importPublicKey(jwkData) {
    if (!jwkData) {
        throw new Error("Chave pública não fornecida.");
    }

    let jwk = jwkData;

    // 1. Se veio como String JSON (ex: do banco Supabase), converte para Objeto
    if (typeof jwk === "string") {
        try {
            jwk = JSON.parse(jwk);
            // Se por acaso estava duplamente envelopado em string
            if (typeof jwk === "string") {
                jwk = JSON.parse(jwk);
            }
        } catch (e) {
            console.error("Erro ao fazer parse da string JWK:", e);
            throw new Error("Formato JSON inválido para a chave pública.");
        }
    }

    // 2. Normaliza e garante todos os campos obrigatórios da especificação JWK para RSA-OAEP
    const normalizedJwk = {
        kty: jwk.kty || "RSA",
        alg: "RSA-OAEP-256",
        ext: true,
        key_ops: ["encrypt"],
        e: jwk.e,
        n: jwk.n
    };

    if (!normalizedJwk.n || !normalizedJwk.e) {
        console.error("Objeto JWK incompleto recebido:", jwk);
        throw new Error("JWK ausente dos componentes 'n' ou 'e'.");
    }

    // 3. Importa utilizando a Web Crypto API nativa do navegador
    return await window.crypto.subtle.importKey(
        "jwk",
        normalizedJwk,
        {
            name: "RSA-OAEP",
            hash: "SHA-256"
        },
        true,
        ["encrypt"]
    );
}


/**
 * Cifra uma mensagem em texto puro usando a CryptoKey pública do destinatário.
 * 
 * @param {string} plainText - O texto simples a ser cifrado.
 * @param {CryptoKey} recipientPublicKey - A CryptoKey pública do destinatário.
 * @return {Promise<string>} O texto cifrado codificado em formato Base64.
 */
export async function encryptMessage(plainText, recipientPublicKey) {
    if (!plainText) return "";
    if (!recipientPublicKey) {
        throw new Error("Chave pública do destinatário não fornecida.");
    }

    const encoder = new TextEncoder();
    const data = encoder.encode(plainText);

    // Cifra o buffer de dados utilizando RSA-OAEP
    const encryptedBuffer = await crypto.subtle.encrypt(
        {
            name: "RSA-OAEP"
        },
        recipientPublicKey,
        data
    );

    // Converte o ArrayBuffer cifrado em string Base64 para envio via JSON/WS
    const binaryString = String.fromCharCode(...new Uint8Array(encryptedBuffer));
    return btoa(binaryString);
}

/**
 * Decifra uma mensagem cifrada em formato Base64 usando a chave privada local do usuário.
 * 
 * @param {string} ciphertextBase64 - A mensagem cifrada recebida em Base64.
 * @param {CryptoKey} privateKey - A CryptoKey privada local (salva no IndexedDB).
 * @return {Promise<string>} O texto simples decifrado.
 */
export async function decryptMessage(ciphertextBase64, privateKey) {
    if (!ciphertextBase64) return "";
    if (!privateKey) {
        throw new Error("Chave privada local não fornecida.");
    }

    // Decodifica a string Base64 para ArrayBuffer
    const binaryString = atob(ciphertextBase64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }

    // Decifra o buffer utilizando a chave privada local
    const decryptedBuffer = await crypto.subtle.decrypt(
        {
            name: "RSA-OAEP"
        },
        privateKey,
        bytes.buffer
    );

    const decoder = new TextDecoder();
    return decoder.decode(decryptedBuffer);
}
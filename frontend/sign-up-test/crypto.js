export class Crypto {
    constructor(iteration = 600_000) {
        this.iterations = iterations;
    }
    
    toBase64(bytes) {
        let binary = "";
    
        for (const byte of bytes) {
            binary += String.fromCharCode(byte);
        }
    
        return btoa(binary);
    }
    
    
    async encryptBackup(privateKey, password) {
        const encoder = new TextEncoder();
    
        const salt = crypto.getRandomValues(
            new Uint8Array(16)
        );
    
        const iv = crypto.getRandomValues(
            new Uint8Array(12)
        );
    
        const passwordKey = await crypto.subtle.importKey(
            "raw",
            encoder.encode(password),
            "PBKDF2",
            false,
            ["deriveKey"]
        );
    
        const encryptionKey = await crypto.subtle.deriveKey(
            {
                name: "PBKDF2",
                salt,
                iterations: iterations,
                hash: "SHA-256"
            },
            passwordKey,
            {
                name: "AES-GCM",
                length: 256
            },
            false,
            ["encrypt"]
        );
    
        const plaintext = encoder.encode(
            JSON.stringify(privateKey)
        );
    
        const ciphertext = await crypto.subtle.encrypt(
            {
                name: "AES-GCM",
                iv
            },
            encryptionKey,
            plaintext
        );
    
        return {
            version: 1,
            iterations: this.iterations,
            salt: this.toBase64(salt),
            iv: this.toBase64(iv),
            ciphertext: this.toBase64(
                new Uint8Array(ciphertext)
            )
        };
    }
    
    async createRegistrationKeys(
        backupPassword
    ) {
        const pair =
            await crypto.subtle.generateKey(
                {
                    name: "ECDH",
                    namedCurve: "P-256"
                },
                true,
                ["deriveKey", "deriveBits"]
            );
        
        const publicKey =
            await crypto.subtle.exportKey(
                "jwk",
                pair.publicKey
            );
    
        const privateKey =
            await crypto.subtle.exportKey(
                "jwk",
                pair.privateKey
            );
    
        const encryptedBackup =
            await this.encryptBackup(
                privateKey,
                backupPassword
            );
    
        return {
            publicKey,
            encryptedBackup
        };
    }
}
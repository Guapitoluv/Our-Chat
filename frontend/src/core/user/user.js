export class User {
    /**
     * @param {Object} userData - Objeto contendo os dados do usuário do backend
     * @param {string} userData.id
     * @param {string} userData.name
     * @param {string} userData.email
     * @param {string} [userData.role="user"]
     * @param {Object} [userData.publicKey=null]
     * @param {string} [userData.createdAt=null]
     */
    constructor({ id = null, name = null, email = null, role = "user", publicKey = null, createdAt = null } = {}) {
        this.id = id;
        this.name = name;
        this.email = email;
        this.role = role;
        this.publicKey = publicKey;
        this.createdAt = createdAt;
    }

    /**
     * Helper para verificar se o usuário possui permissão de admin.
     */
    get isAdmin() {
        return this.role === "admin";
    }

    /**
     * Converte a instância de volta para um objeto simples JSON (sem métodos).
     */
    toJSON() {
        return {
            id: this.id,
            name: this.name,
            email: this.email,
            role: this.role,
            publicKey: this.publicKey,
            createdAt: this.createdAt
        };
    }
}
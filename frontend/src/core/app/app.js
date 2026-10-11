import { User } from "../user/user.js";

export class App {
    constructor(router, wsClient, user) {
        this.router = router;
        this.ws = wsClient;
        this.user = user;
        
        // Carrega o perfil do localStorage IMEDIATAMENTE na construção do App
        this.#loadSavedProfile();
    }

    #loadSavedProfile() {
        const savedProfile = localStorage.getItem("user_profile");
        if (savedProfile) {
            try {
                const userData = JSON.parse(savedProfile);
                // Atualiza as propriedades da instância sem perder a referência
                Object.assign(this.user, new User(userData));
            } catch (err) {
                console.error("Erro ao restaurar perfil do localStorage:", err);
            }
        }
    }

    async init() {
        // Conecta ao WebSocket em segundo plano
        await this.ws.connect();
    }
}

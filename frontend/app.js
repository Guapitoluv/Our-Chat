import { WebSocketClient } from "./src/services/websocket.js";
import { Router } from "./src/core/router/router.js";
import { User } from "./src/core/user/user.js";
import { App } from "./src/core/app/app.js";

try {
    const wsClient = new WebSocketClient(
        "wss://our-chat-1gz3.onrender.com/ws"
    );
    const router = new Router();
    
    // Instância base do usuário
    const user = new User();
    
    // 1. Instancia o App
    const app = new App(router, wsClient, user);
    
    // 2. Define o Contexto Global (Mantendo 'user' e 'app' para compatibilidade total)
    router.setContext({ app, router, ws: wsClient, user });

    // 3. Importação das Páginas
    const { IndexPage } = await import("./src/pages/index/index.js");
    const { SignUpPage } = await import("./src/pages/sign-up/sign-up.js");
    const { ConversationPage } = await import("./src/pages/conversation/conversation.js");
    const { SignInPage } = await import("./src/pages/sign-in/sign-in.js");

    // 4. Registo de Rotas
    router.registerRoute("/", {
        page: IndexPage,
        css: [
            "./src/pages/index/css/index.css",
            "./public/fonts/silkscreen/silkscreen.css",
            "./src/pages/index/css/profile-flyout.css"
        ]
    });

    router.registerRoute("/conversation", {
        page: ConversationPage,
        css: [
            "./src/pages/conversation/conversation.css",
            "./public/fonts/silkscreen/silkscreen.css"
        ]
    });

    router.registerRoute("/sign-up", {
        page: SignUpPage,
        css: [
            "./src/pages/sign-up/sign-up.css",
            "./public/fonts/silkscreen/silkscreen.css"
        ]
    });

    router.registerRoute("/sign-in", {
        page: SignInPage,
        css: [
            "./src/pages/sign-in/sign-in.css",
            "./public/fonts/silkscreen/silkscreen.css"
        ]
    });

    // 5. PRIMEIRO: Renderiza a UI imediatamente (NÃO trava a tela em branco)
    await router.renderRoute();

    // 6. DEPOIS: Inicializa WS e restaura dados em segundo plano
    app.init().catch((err) => {
        console.warn("WS não conectou imediatamente, a UI responderá via eventos:", err);
    });

} catch (error) {
    const el = document.createElement("p");
    el.innerHTML = `==== ERROR ========<br>name: ${error.name}<br>message: ${error.message}<br>stack: ${error.stack}`;
    el.classList.add("console-error");
    document.body.prepend(el);
}

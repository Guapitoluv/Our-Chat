import { router } from "./router-instance.js";

try {
    const indexModule = await import(
        "./src/pages/index/index.js"
    );
    const IndexPage =
        indexModule.IndexPage;
    
    const conversationModule = await import(
         "./src/pages/conversation/conversation.js"
    );
    const ConversationPage =
        conversationModule.ConversationPage;
    
    router.registerRoute(
        "/",
        {
            page: IndexPage,
            
            css: [
                "/src/pages/index/index.css",
                "/public/fonts/silkscreen/silkscreen.css"
            ]
        }
    );
    
    router.registerRoute(
        "/conversation",
        {
            page: ConversationPage,
            
            css: [
                "/src/pages/conversation/conversation.css",
                "/public/fonts/silkscreen/silkscreen.css"
            ]
        }
    );
    
    
    router.renderRoute();
    
} catch (error) {
    const el = document.createElement("p");
    el.innerHTML =
        `==== ERROR ========<br>name: ${error.name}<br>message: ${error.message}<br>stack: ${error.stack}`;
    el.classList.add("console-error");
    document.body.prepend(el);
}
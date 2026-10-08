export class Router {

    #routes = new Map();

    #currentPage = null;
    #currentStyles = [];
    
    constructor() {
        this.#setupEvents();
    }
    
    // ============================================================
    // ROTAS
    // ============================================================

    registerRoute(path, config) {
        this.#routes.set(
            path,
            config
        );
    }
    
    // ============================================================
    // NAVEGAÇÃO
    // ============================================================

    async navigate(
        path,
        replace = false
    ) {
        if (!this.#routes.has(path)) {
            console.error(
                `Rota não encontrada: ${path}`
            );

            return;
        }
        
        if (replace) {
            history.replaceState(
                {},
                "",
                path
            );
        } else {
            history.pushState(
                {},
                "",
                path
            );
        }
        
        await this.renderRoute(path);
    }
    
    
    #loadStyle(css) {
        return new Promise(
            resolve => {
                const style =
                    document.createElement(
                        "link"
                    );
                
                style.rel = "stylesheet";
                style.href =
                    `${css}?v=${Date.now()}`;
                
                style.onload =
                    () => resolve(style);
                
                style.onerror =
                    () => {
                        console.error(
                            `Erro ao carregar CSS: ${css}`
                        );
    
                        resolve(style);
                    };
                
                document.head.appendChild(
                    style
                );
            }
        );
    }
    
    
    async renderRoute(
        path = location.pathname
    ) {
        const route =
            this.#routes.get(path);
    
        if (!route) {
            console.error(
                `Rota não encontrada: ${path}`
            );
    
            return;
        }
    
        // ========================================================
        // 1. Cria e carrega a nova página
        // ========================================================
    
        const page =
            new route.page();
    
        await page.load();
        
        // ========================================================
        // 2. Carrega CSS da nova página
        // ========================================================
    
        const newStyles = [];
        
        if (route.css) {
            for (const css of route.css) {
                const style =
                    await this.#loadStyle(css);
                
                newStyles.push(
                    style
                );
            }
        }
        
        // ========================================================
        // 3. Guarda a página e os estilos atuais
        // ========================================================
    
        const oldPage =
            this.#currentPage;
    
        const oldStyles =
            this.#currentStyles;
        
        // ========================================================
        // 4. Troca a página
        // ========================================================
    
        const app =
            document.querySelector(
                "#app"
            );
        
        app.replaceChildren(
            page.element
        );
        
        // ========================================================
        // 5. Inicializa a nova página
        // ========================================================
    
        page.mount();
        
        // ========================================================
        // 6. Desmonta a página anterior
        // ========================================================
    
        if (oldPage) {
            oldPage.unmount();
        }
        
        // ========================================================
        // 7. Remove CSS anterior
        // ========================================================
    
        oldStyles.forEach(
            css => css.remove()
        );
        
        // ========================================================
        // 8. Atualiza referências
        // ========================================================
    
        this.#currentPage = page;
    
        this.#currentStyles =
            newStyles;
    }
    
    // ============================================================
    // EVENTOS DO ROUTER
    // ============================================================

    #setupEvents() {
        // Voltar / avançar do navegador
        window.addEventListener(
            "popstate",
            () => {
                this.renderRoute();
            }
        );
        
        // Links SPA
        document.addEventListener(
            "click",
            event => {
                const link =
                    event.target.closest(
                        "a[data-route]"
                    );
                
                if (
                    !link
                    || event.button !== 0
                    || event.ctrlKey
                    || event.shiftKey
                    || event.altKey
                    || event.metaKey
                ) {
                    return;
                }
                
                event.preventDefault();
                
                this.navigate(
                    link.pathname
                );
            }
        );
    }
}
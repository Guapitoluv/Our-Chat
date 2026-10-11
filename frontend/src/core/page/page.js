export class Page {
    constructor(htmlPath) {
        this.htmlPath = htmlPath;
        this.element = null;
        this.context = null;
    }


    async load() {
        const response =
            await fetch(
                this.htmlPath,
                {
                    cache: "no-store"
                }
            );
        
        if (!response.ok) {
            throw new Error(
                `Erro ao carregar página: ${response.status}`
            );
        }
        
        const html =
            await response.text();
        
        const template =
            document.createElement("template");

        template.innerHTML =
            html.trim();


        this.element =
            template.content.firstElementChild;


        if (!this.element) {
            throw new Error(
                "O HTML da página está vazio."
            );
        }


        return this;
    }


    mount(context) {
        this.context = context;
    }


    unmount() {
        this.context = null;
    }
}
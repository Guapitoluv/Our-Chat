export async function createTestPage() {

    /*
     * Busca o HTML
     */

    const response = await fetch(
        "/src/pages/test/test.html"
    );


    if (!response.ok) {
        throw new Error(
            `Erro ao carregar test.html: ${response.status}`
        );
    }


    const html = await response.text();


    /*
     * Transforma o HTML em elementos DOM
     */

    const template =
        document.createElement("template");

    template.innerHTML = html;


    const element =
        template.content.firstElementChild;


    /*
     * Executado depois que a página
     * entrou no #app
     */

    function mount() {

        const button =
            element.querySelector("#test-button");


        button.addEventListener(
            "click",
            () => {

                console.log(
                    "Botão da página Test clicado."
                );

            }
        );
    }


    /*
     * Executado antes de sair da página
     */

    function unmount() {

        console.log(
            "Saindo da página Test."
        );
    }


    return {
        element,
        mount,
        unmount
    };
}
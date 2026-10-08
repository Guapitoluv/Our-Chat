async function f() {
    const response = await fetch(
        "to-fetch.html"
    );
    const html = await response.text();
    const main = document.querySelector("main");
    
    main.innerHTML = html;
}

f();
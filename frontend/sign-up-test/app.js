import { Crypto } from "./crypto.js";

const form = document.querySelector("#register-form");
const button = document.querySelector("#submit-button");
const status = document.querySelector("#status");
const myCrypto = new Crypto();

function setStatus(message) {
    status.textContent = message;
}

function connectWebSocket() {
    return new Promise((resolve, reject) => {
        const ws = new WebSocket(
            "wss://our-chat-1gz3.onrender.com/ws"
        );

        ws.addEventListener("open", () => {
            resolve(ws);
        }, { once: true });

        ws.addEventListener("error", () => {
            reject(new Error("Não foi possível conectar ao servidor."));
        }, { once: true });
    });
}

function waitForResponse(ws, requestId) {
    return new Promise((resolve, reject) => {
        function cleanup() {
            ws.removeEventListener("message", onMessage);
            ws.removeEventListener("error", onError);
            ws.removeEventListener("close", onClose);
        }

        function onMessage(event) {
            let message;

            try {
                message = JSON.parse(event.data);
            } catch {
                return;
            }

            if (message.requestId !== requestId) {
                return;
            }

            cleanup();
            resolve(message);
        }

        function onError() {
            cleanup();
            reject(new Error("Erro na conexão WebSocket."));
        }

        function onClose() {
            cleanup();
            reject(new Error("A conexão foi encerrada."));
        }

        ws.addEventListener("message", onMessage);
        ws.addEventListener("error", onError);
        ws.addEventListener("close", onClose);
    });
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    button.disabled = true;
    setStatus("Preparando cadastro...");

    let ws;

    try {
        const name = form.elements.name.value.trim();
        const email = form.elements.email.value.trim();
        const password = form.elements.password.value;
        const backupPassword =
            form.elements.backupPassword.value;

        if (password.length < 8) {
            throw new Error(
                "A senha da conta precisa ter pelo menos 8 caracteres."
            );
        }

        if (backupPassword.length < 12) {
            throw new Error(
                "A senha de recuperação precisa ter pelo menos 12 caracteres."
            );
        }

        const { publicKey, encryptedBackup } =
            await myCrypto.createRegistrationKeys(backupPassword);

        ws = await connectWebSocket();

        const requestId = crypto.randomUUID();

        const responsePromise = waitForResponse(
            ws,
            requestId
        );

        ws.send(JSON.stringify({
            type: "sign_up",
            requestId,
            payload: {
                name,
                email,
                password,
                publicKey,
                encryptedBackup
            }
        }));

        setStatus("Aguardando resposta do servidor...");

        const response = await responsePromise;

        if (response.type === "sign_up_success") {
            setStatus(
                `Cadastro concluído! ID: ${response.payload.userId}`
            );

            form.reset();
        } else if (response.type === "error") {
            setStatus(
                response.payload?.message || "O cadastro falhou."
            );
        } else {
            setStatus("Resposta inesperada do servidor.");
        }
    } catch (error) {
        setStatus(error.message || "Ocorreu um erro.");
    } finally {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.close();
        }

        button.disabled = false;
    }
})

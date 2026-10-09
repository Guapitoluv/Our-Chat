import json
import os
import re
import uuid
from pathlib import Path

import aiosqlite
from aiohttp import web
from argon2 import PasswordHasher
from argon2.exceptions import HashingError

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

DATABASE_PATH = Path(
    os.environ.get(
        "DATABASE_PATH",
        str(DATA_DIR / "our_chat_dev.sqlite3")
    )
)

password_hasher = PasswordHasher()


async def initialize_database():
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                public_key TEXT NOT NULL,
                encrypted_backup TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()


async def health_check(request):
    """Endpoint HTTP simples para verificar se a API está ativa no Render."""
    return web.json_response({
        "status": "ok",
        "service": "OurChat API"
    })


async def websocket_handler(request):
    ws = web.WebSocketResponse(
        heartbeat=30
    )

    await ws.prepare(request)

    print("Cliente conectado via WebSocket.")

    try:
        async for message in ws:
            if message.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(message.data)

                    if not isinstance(data, dict):
                        raise ValueError("Formato inválido.")

                    message_type = data.get("type")
                    request_id = data.get("requestId")
                    payload = data.get("payload")

                    if not isinstance(request_id, str):
                        raise ValueError("requestId inválido.")

                    if not isinstance(payload, dict):
                        raise ValueError("payload inválido.")

                    if message_type == "sign_up":
                        await handle_sign_up(
                            ws,
                            request_id,
                            payload
                        )
                    else:
                        await send_error(
                            ws,
                            request_id,
                            "Tipo de mensagem desconhecido."
                        )

                except (
                    json.JSONDecodeError,
                    ValueError,
                    TypeError
                ):
                    await send_error(
                        ws,
                        None,
                        "Mensagem inválida."
                    )

            elif message.type == web.WSMsgType.ERROR:
                print("Erro WebSocket:", ws.exception())

    finally:
        print("Cliente desconectado.")

    return ws


async def handle_sign_up(ws, request_id, payload):
    name = payload.get("name")
    email = payload.get("email")
    password = payload.get("password")
    public_key = payload.get("publicKey")
    encrypted_backup = payload.get("encryptedBackup")

    if not all([
        isinstance(name, str),
        isinstance(email, str),
        isinstance(password, str),
        isinstance(public_key, dict),
        isinstance(encrypted_backup, dict)
    ]):
        await send_error(
            ws,
            request_id,
            "Preencha todos os campos corretamente."
        )
        return

    name = name.strip()
    email = email.strip().lower()

    if not name or len(name) > 80:
        await send_error(
            ws,
            request_id,
            "O nome deve ter entre 1 e 80 caracteres."
        )
        return

    if len(email) > 254 or not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        email
    ):
        await send_error(
            ws,
            request_id,
            "E-mail inválido."
        )
        return

    if len(password) < 8 or len(password) > 128:
        await send_error(
            ws,
            request_id,
            "A senha deve ter entre 8 e 128 caracteres."
        )
        return

    # Validação básica da chave pública P-256.
    if not all(
        isinstance(public_key.get(field), str)
        for field in ("kty", "crv", "x", "y")
    ) or (
        public_key.get("kty") != "EC"
        or public_key.get("crv") != "P-256"
    ):
        await send_error(
            ws,
            request_id,
            "Chave pública inválida."
        )
        return

    # O backup deve conter os campos produzidos pelo cliente.
    required_backup_fields = (
        "version",
        "iterations",
        "salt",
        "iv",
        "ciphertext"
    )

    if not all(
        field in encrypted_backup
        for field in required_backup_fields
    ):
        await send_error(
            ws,
            request_id,
            "Backup criptografado inválido."
        )
        return

    try:
        password_hash = password_hasher.hash(password)
    except HashingError:
        await send_error(
            ws,
            request_id,
            "Não foi possível processar a senha."
        )
        return

    user_id = str(uuid.uuid4())

    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                """
                INSERT INTO users (
                    id,
                    name,
                    email,
                    password_hash,
                    public_key,
                    encrypted_backup
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    name,
                    email,
                    password_hash,
                    json.dumps(public_key),
                    json.dumps(encrypted_backup)
                )
            )

            await db.commit()

    except aiosqlite.IntegrityError:
        await send_error(
            ws,
            request_id,
            "Este e-mail já está cadastrado."
        )
        return

    print(f"Cadastro criado: {user_id}")

    await ws.send_json({
        "type": "sign_up_success",
        "requestId": request_id,
        "payload": {
            "userId": user_id,
            "name": name
        }
    })


async def send_error(ws, request_id, message):
    await ws.send_json({
        "type": "error",
        "requestId": request_id,
        "payload": {
            "message": message
        }
    })


async def on_startup(app):
    await initialize_database()
    print(f"Banco de dados inicializado em: {DATABASE_PATH}")


app = web.Application()

# Mapeamento de rotas exclusivas do backend
app.router.add_get("/", health_check)
app.router.add_get("/ws", websocket_handler)

app.on_startup.append(on_startup)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))

    web.run_app(
        app,
        host="0.0.0.0",
        port=port
    )

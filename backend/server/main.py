import json
import os
import re
import uuid

import asyncpg
from aiohttp import web
from argon2 import PasswordHasher
from argon2.exceptions import HashingError

# Pega a URL do ambiente (Render) ou usa a URL informada diretamente em desenvolvimento
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:SUA_SENHA_AQUI@db.SEU_PROJETO_AQUI.supabase.co:5432/postgres"
)

password_hasher = PasswordHasher()


async def initialize_database(app):
    """Cria o pool de conexões assíncronas com o Supabase e cria a tabela se não existir."""
    print("Conectando ao banco de dados Supabase...")
    
    # Cria o pool de conexões reutilizável
    app['db_pool'] = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=5,  # Mantém no máximo 5 conexões abertas por instância
        statement_cache_size=0  # Obrigatório para o Transaction Pooler do Supabase
    )


    async with app['db_pool'].acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                public_key JSONB NOT NULL,
                encrypted_backup JSONB NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
    print("Conexão estabelecida e tabela 'users' pronta!")


async def cleanup_database(app):
    """Fecha a conexão com o Supabase ao desligar o servidor."""
    await app['db_pool'].close()


async def health_check(request):
    return web.json_response({
        "status": "ok",
        "service": "OurChat API (Supabase)"
    })


async def get_users_http(request):
    """Rota HTTP REST para listar usuários salvos no Supabase."""
    db_pool = request.app['db_pool']
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, name, email, public_key, role, created_at 
                FROM users 
                ORDER BY created_at DESC
            """)
            
            users = []
            for row in rows:
                user_dict = dict(row)
                if user_dict.get("created_at"):
                    user_dict["created_at"] = user_dict["created_at"].isoformat()
                
                # Converte o JSONB retornado pelo asyncpg
                if isinstance(user_dict.get("public_key"), str):
                    user_dict["public_key"] = json.loads(user_dict["public_key"])
                users.append(user_dict)

            return web.json_response({"users": users})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def websocket_handler(request):
    ws = web.WebSocketResponse(heartbeat=30)
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
                    payload = data.get("payload", {})

                    if not isinstance(request_id, str):
                        raise ValueError("requestId inválido.")

                    if message_type == "sign_up":
                        if not isinstance(payload, dict):
                            raise ValueError("payload inválido.")
                        await handle_sign_up(request.app['db_pool'], ws, request_id, payload)

                    elif message_type == "get_users":
                        await handle_get_users(request.app['db_pool'], ws, request_id)

                    else:
                        await send_error(ws, request_id, "Tipo de mensagem desconhecido.")

                except (json.JSONDecodeError, ValueError, TypeError):
                    await send_error(ws, None, "Mensagem inválida.")

            elif message.type == web.WSMsgType.ERROR:
                print("Erro WebSocket:", ws.exception())

    finally:
        print("Cliente desconectado.")

    return ws


async def handle_get_users(db_pool, ws, request_id):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, email, public_key, role, created_at 
            FROM users 
            ORDER BY created_at DESC
        """)
        users = []
        for r in rows:
            u = dict(r)
            if u.get("created_at"):
                u["created_at"] = u["created_at"].isoformat()
            users.append(u)

    await ws.send_json({
        "type": "get_users_success",
        "requestId": request_id,
        "payload": {"users": users}
    })


async def handle_sign_up(db_pool, ws, request_id, payload):
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
        await send_error(ws, request_id, "Preencha todos os campos corretamente.")
        return

    name = name.strip()
    email = email.strip().lower()

    if not name or len(name) > 80:
        await send_error(ws, request_id, "O nome deve ter entre 1 e 80 caracteres.")
        return

    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        await send_error(ws, request_id, "E-mail inválido.")
        return

    if len(password) < 8 or len(password) > 128:
        await send_error(ws, request_id, "A senha deve ter entre 8 e 128 caracteres.")
        return

    try:
        password_hash = password_hasher.hash(password)
    except HashingError:
        await send_error(ws, request_id, "Não foi possível processar a senha.")
        return

    user_id = str(uuid.uuid4())

    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (
                    id, name, email, password_hash, public_key, encrypted_backup
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                user_id,
                name,
                email,
                password_hash,
                json.dumps(public_key),
                json.dumps(encrypted_backup)
            )

    except asyncpg.UniqueViolationError:
        await send_error(ws, request_id, "Este e-mail já está cadastrado.")
        return

    print(f"Cadastro criado no Supabase: {user_id}")

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
        "payload": {"message": message}
    })


app = web.Application()

app.router.add_get("/", health_check)
app.router.add_get("/api/users", get_users_http)
app.router.add_get("/ws", websocket_handler)

app.on_startup.append(initialize_database)
app.on_cleanup.append(cleanup_database)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    web.run_app(app, host="0.0.0.0", port=port)

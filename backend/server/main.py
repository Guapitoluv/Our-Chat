import json
import os
import re
import uuid

import asyncpg
from aiohttp import web
from argon2 import PasswordHasher
from argon2.exceptions import HashingError

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("A variável de ambiente DATABASE_URL não foi definida!")

password_hasher = PasswordHasher()


async def initialize_database(app):
    """Inicializa o pool do banco de dados e cria tabelas se não existirem."""
    print("Conectando ao banco de dados Supabase...")

    app['db_pool'] = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=5,
        statement_cache_size=0
    )

    app['active_connections'] = {}  # Mapeia user_id -> WebSocketResponse

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
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                requester_id TEXT NOT NULL REFERENCES users(id),
                recipient_id TEXT NOT NULL REFERENCES users(id),
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id),
                sender_id TEXT NOT NULL REFERENCES users(id),
                ciphertext TEXT NOT NULL,
                iv TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
    print("Tabelas prontas para uso!")


async def cleanup_database(app):
    if 'db_pool' in app:
        await app['db_pool'].close()


def format_user_row(row):
    user = dict(row)
    if user.get("created_at"):
        user["created_at"] = user["created_at"].isoformat()
    if isinstance(user.get("public_key"), str):
        user["public_key"] = json.loads(user["public_key"])
    if isinstance(user.get("encrypted_backup"), str):
        user["encrypted_backup"] = json.loads(user["encrypted_backup"])
    return user


def format_user_payload(user_row):
    user_data = format_user_row(user_row)
    return {
        "id": user_data["id"],
        "name": user_data["name"],
        "email": user_data["email"],
        "role": user_data.get("role", "user"),
        "publicKey": user_data.get("public_key"),
        "createdAt": user_data.get("created_at")
    }


async def send_error(ws, request_id, message):
    await ws.send_json({
        "type": "error",
        "requestId": request_id,
        "payload": {"message": message}
    })


async def websocket_handler(request):
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    ws.user_id = None
    active_connections = request.app['active_connections']

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

                    if message_type == "authenticate":
                        await handle_authenticate(request.app, ws, request_id, payload)
                    elif message_type == "sign_up":
                        await handle_sign_up(request.app, ws, request_id, payload)
                    elif message_type == "sign_in":
                        await handle_sign_in(request.app, ws, request_id, payload)
                    elif message_type == "get_users":
                        await handle_get_users(request.app['db_pool'], ws, request_id)
                    elif message_type == "get_conversations":
                        await handle_get_conversations(request.app, ws, request_id)
                    elif message_type == "conversation_request":
                        await handle_conversation_request(request.app, ws, request_id, payload)
                    elif message_type == "conversation_response":
                        await handle_conversation_response(request.app, ws, request_id, payload)
                    elif message_type == "send_message":
                        await handle_send_message(request.app, ws, request_id, payload)
                    else:
                        await send_error(ws, request_id, "Tipo de mensagem desconhecido.")

                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    await send_error(ws, None, f"Mensagem inválida: {str(e)}")

            elif message.type == web.WSMsgType.ERROR:
                print("Erro WebSocket:", ws.exception())

    finally:
        if ws.user_id and ws.user_id in active_connections:
            del active_connections[ws.user_id]
        print(f"Cliente {ws.user_id or ''} desconectado.")

    return ws


async def handle_authenticate(app, ws, request_id, payload):
    user_id = payload.get("userId")
    if not user_id:
        await send_error(ws, request_id, "userId é obrigatório para autenticação.")
        return

    ws.user_id = user_id
    app['active_connections'][user_id] = ws

    await ws.send_json({
        "type": "authenticate_success",
        "requestId": request_id,
        "payload": {"status": "authenticated", "userId": user_id}
    })


async def handle_sign_up(app, ws, request_id, payload):
    name = payload.get("name")
    email = payload.get("email")
    password = payload.get("password")
    public_key = payload.get("publicKey")
    encrypted_backup = payload.get("encryptedBackup")

    if not all([isinstance(name, str), isinstance(email, str), isinstance(password, str)]):
        await send_error(ws, request_id, "Preencha todos os campos.")
        return

    email = email.strip().lower()
    password_hash = password_hasher.hash(password)
    user_id = str(uuid.uuid4())

    try:
        async with app['db_pool'].acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (id, name, email, password_hash, public_key, encrypted_backup)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, name, email, role, public_key, created_at
                """,
                user_id, name.strip(), email, password_hash,
                json.dumps(public_key), json.dumps(encrypted_backup)
            )
    except asyncpg.UniqueViolationError:
        await send_error(ws, request_id, "E-mail já cadastrado.")
        return

    ws.user_id = user_id
    app['active_connections'][user_id] = ws

    await ws.send_json({
        "type": "sign_up_success",
        "requestId": request_id,
        "payload": {"user": format_user_payload(row)}
    })


async def handle_sign_in(app, ws, request_id, payload):
    email = payload.get("email", "").strip().lower()
    password = payload.get("password", "")

    async with app['db_pool'].acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
        if not row:
            await send_error(ws, request_id, "E-mail ou senha incorretos.")
            return

        try:
            password_hasher.verify(row["password_hash"], password)
        except Exception:
            await send_error(ws, request_id, "E-mail ou senha incorretos.")
            return

        user_data = format_user_row(row)
        ws.user_id = user_data["id"]
        app['active_connections'][ws.user_id] = ws

        await ws.send_json({
            "type": "sign_in_success",
            "requestId": request_id,
            "payload": {
                "user": format_user_payload(row),
                "encryptedBackup": user_data["encrypted_backup"]
            }
        })


async def handle_get_users(db_pool, ws, request_id):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, name, email, public_key, role, created_at FROM users ORDER BY name ASC")
        users = [format_user_payload(r) for r in rows]

    await ws.send_json({
        "type": "get_users_success",
        "requestId": request_id,
        "payload": {"users": users}
    })


async def handle_get_conversations(app, ws, request_id):
    """Retorna todas as conversas das quais o usuário conectado faz parte."""
    if not ws.user_id:
        await send_error(ws, request_id, "Não autenticado.")
        return

    async with app['db_pool'].acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, requester_id, recipient_id, status, created_at, updated_at
            FROM conversations
            WHERE requester_id = $1 OR recipient_id = $1
            ORDER BY updated_at DESC
            """,
            ws.user_id
        )

        conversations = []
        for r in rows:
            conversations.append({
                "id": r["id"],
                "requesterId": r["requester_id"],
                "recipientId": r["recipient_id"],
                "otherUserId": r["recipient_id"] if r["requester_id"] == ws.user_id else r["requester_id"],
                "status": r["status"],
                "createdAt": r["created_at"].isoformat() if r["created_at"] else None
            })

    await ws.send_json({
        "type": "get_conversations_success",
        "requestId": request_id,
        "payload": {"conversations": conversations}
    })


async def handle_conversation_request(app, ws, request_id, payload):
    if not ws.user_id:
        await send_error(ws, request_id, "Não autenticado.")
        return

    recipient_id = payload.get("recipientId")
    if not recipient_id:
        await send_error(ws, request_id, "recipientId obrigatório.")
        return

    async with app['db_pool'].acquire() as conn:
        # BUSCA BI-DIRECIONAL: Checa se A -> B ou B -> A já existe
        existing_conv = await conn.fetchrow(
            """
            SELECT id, requester_id, recipient_id, status FROM conversations 
            WHERE (requester_id = $1 AND recipient_id = $2)
               OR (requester_id = $2 AND recipient_id = $1)
            """,
            ws.user_id, recipient_id
        )

        if existing_conv:
            conversation_id = existing_conv["id"]
            conv_status = existing_conv["status"]
            requester_id = existing_conv["requester_id"]
        else:
            conversation_id = str(uuid.uuid4())
            conv_status = "pending"
            requester_id = ws.user_id
            await conn.execute(
                """
                INSERT INTO conversations (id, requester_id, recipient_id, status)
                VALUES ($1, $2, $3, $4)
                """,
                conversation_id, ws.user_id, recipient_id, conv_status
            )

    # Responde para quem pediu
    await ws.send_json({
        "type": "conversation_request_sent",
        "requestId": request_id,
        "payload": {
            "conversationId": conversation_id,
            "status": conv_status,
            "requesterId": requester_id
        }
    })

    # Notifica o destinatário em tempo real se for uma nova solicitação pendente
    if conv_status == "pending" and requester_id == ws.user_id:
        recipient_ws = app['active_connections'].get(recipient_id)
        if recipient_ws:
            await recipient_ws.send_json({
                "type": "incoming_conversation_request",
                "payload": {
                    "conversationId": conversation_id,
                    "requesterId": ws.user_id
                }
            })


async def handle_conversation_response(app, ws, request_id, payload):
    if not ws.user_id:
        await send_error(ws, request_id, "Não autenticado.")
        return

    conversation_id = payload.get("conversationId")
    accepted = bool(payload.get("accepted"))
    status_str = "accepted" if accepted else "rejected"

    async with app['db_pool'].acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE conversations 
            SET status = $1, updated_at = CURRENT_TIMESTAMP
            WHERE id = $2 AND (recipient_id = $3 OR requester_id = $3)
            RETURNING requester_id, recipient_id
            """,
            status_str, conversation_id, ws.user_id
        )

        if not row:
            await send_error(ws, request_id, "Conversa não encontrada ou não autorizada.")
            return

        other_user_id = row["requester_id"] if row["recipient_id"] == ws.user_id else row["recipient_id"]

    await ws.send_json({
        "type": "conversation_response_success",
        "requestId": request_id,
        "payload": {"conversationId": conversation_id, "accepted": accepted}
    })

    # Notifica a outra ponta sobre o aceite/recusa
    other_ws = app['active_connections'].get(other_user_id)
    if other_ws:
        await other_ws.send_json({
            "type": "conversation_status_updated",
            "payload": {
                "conversationId": conversation_id,
                "accepted": accepted,
                "responderId": ws.user_id
            }
        })


async def handle_send_message(app, ws, request_id, payload):
    if not ws.user_id:
        await send_error(ws, request_id, "Não autenticado.")
        return

    conversation_id = payload.get("conversationId")

    # Trata o payload se o ciphertext vier na raiz ou aninhado em 'message'
    message_data = payload.get("message") or {}
    ciphertext = payload.get("ciphertext") or message_data.get("ciphertext")
    iv = payload.get("iv") or message_data.get("iv")

    if not conversation_id or not ciphertext:
        await send_error(ws, request_id, "Dados de mensagem incompletos.")
        return

    async with app['db_pool'].acquire() as conn:
        conv = await conn.fetchrow(
            """
            SELECT requester_id, recipient_id, status FROM conversations 
            WHERE id = $1 AND (requester_id = $2 OR recipient_id = $2)
            """,
            conversation_id, ws.user_id
        )

        if not conv:
            await send_error(ws, request_id, "Conversa não encontrada.")
            return

        message_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO messages (id, conversation_id, sender_id, ciphertext, iv)
            VALUES ($1, $2, $3, $4, $5)
            """,
            message_id, conversation_id, ws.user_id, ciphertext, iv
        )

        target_id = conv["recipient_id"] if conv["requester_id"] == ws.user_id else conv["requester_id"]

    # Confirmação para quem enviou
    await ws.send_json({
        "type": "send_message_success",
        "requestId": request_id,
        "payload": {"messageId": message_id, "conversationId": conversation_id}
    })

    # Transmite para o destinatário em tempo real
    target_ws = app['active_connections'].get(target_id)
    if target_ws:
        await target_ws.send_json({
            "type": "new_message",
            "payload": {
                "messageId": message_id,
                "conversationId": conversation_id,
                "senderId": ws.user_id,
                "ciphertext": ciphertext,
                "iv": iv
            }
        })


app = web.Application()
app.router.add_get("/ws", websocket_handler)

app.on_startup.append(initialize_database)
app.on_cleanup.append(cleanup_database)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    web.run_app(app, host="0.0.0.0", port=port)
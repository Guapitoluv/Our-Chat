import os
import json
import asyncio
from pathlib import Path
from functools import partial
from typing import Any, Callable, Awaitable

import asyncpg
from aiohttp import web
from argon2 import PasswordHasher
# Em backend/server/main.py

import sys
from pathlib import Path

# Adiciona a raiz do projeto (/opt/render/project/src) e a pasta do server ao sys.path
SERVER_DIR = Path(__file__).resolve().parent
ROOT_DIR = SERVER_DIR.parent.parent

for path in [str(SERVER_DIR), str(ROOT_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

# ================================================================
# IMPORTS DOS HANDLERS (Usando imports simples sem o prefixo 'backend.')
# ================================================================

from handlers.send_message_handler import SendMessageHandler
from handlers.authentication_handler import AuthenticationHandler
from handlers.sign_up_handler import SignUpHandler
from handlers.sign_in_handler import SignInHandler
from handlers.get_messages_handler import GetMessagesHandler
from handlers.conversation_response_handler import ConversationResponseHandler
from handlers.conversation_request_handler import ConversationRequestHandler
from handlers.get_conversations_handler import GetConversationsHandler
from handlers.get_users_handler import GetUsersHandler

from authenticated_websocket import AuthenticatedWebSocket
from initialize_db import initialize_database


# ================================================================
# CONFIGURAÇÕES E VARIÁVEIS DE AMBIENTE
# ================================================================

DATABASE_URL: str | None = os.environ.get("DATABASE_URL")
JWT_SECRET: str | None = os.environ.get("JWT_SECRET")

if not DATABASE_URL:
    raise ValueError("A variável de ambiente DATABASE_URL não foi definida!")

if not JWT_SECRET:
    raise ValueError("A variável de ambiente JWT_SECRET não foi definida!")

password_hasher: PasswordHasher = PasswordHasher()


# ================================================================
# INSTÂNCIAS DOS HANDLERS (COM INJEÇÃO DE DEPENDÊNCIAS)
# ================================================================

send_message_handler = SendMessageHandler()
authentication_handler = AuthenticationHandler(jwt_secret=JWT_SECRET)
sign_up_handler = SignUpHandler(password_hasher=password_hasher, jwt_secret=JWT_SECRET)
sign_in_handler = SignInHandler(password_hasher=password_hasher, jwt_secret=JWT_SECRET)
get_messages_handler = GetMessagesHandler()
conversation_response_handler = ConversationResponseHandler()
conversation_request_handler = ConversationRequestHandler()
get_conversations_handler = GetConversationsHandler()
get_users_handler = GetUsersHandler()


# ================================================================
# CICLO DE VIDA DO BANCO DE DADOS E APLICAÇÃO
# ================================================================


async def cleanup_database(app: web.Application) -> None:
    """Encerra o pool de conexões com o banco de dados ao fechar o servidor."""
    if 'db_pool' in app:
        pool: asyncpg.Pool = app['db_pool']
        await pool.close()
        print("Pool de conexões com o banco de dados encerrado.")


# ================================================================
# DISPATCHER DE MENSAGENS WEBSOCKET
# ================================================================

async def dispatch_message(
    app: web.Application, 
    ws: AuthenticatedWebSocket, 
    request_id: str, 
    message_type: str, 
    payload: dict[str, Any]
) -> None:
    """Mapeia os tipos de mensagem recebidos via WebSocket para seus respectivos handlers."""
    
    # Mapeamento com assinatura padronizada: (app, ws, request_id, payload)
    handlers: dict[str, Callable[[web.Application, AuthenticatedWebSocket, str, dict[str, Any]], Awaitable[None]]] = {
        "authenticate": authentication_handler.handle_authenticate,
        "sign_up": sign_up_handler.handle_sign_up,
        "sign_in": sign_in_handler.handle_sign_in,
        "get_users": get_users_handler.handle_get_users,
        "get_conversations": get_conversations_handler.handle_get_conversations,
        "get_messages": get_messages_handler.handle_get_messages,
        "conversation_request": conversation_request_handler.handle_conversation_request,
        "conversation_response": conversation_response_handler.handle_conversation_response,
        "send_message": send_message_handler.handle_send_message,
    }

    handler = handlers.get(message_type)
    
    if handler:
        await handler(app, ws, request_id, payload)
    else:
        await ws.send_error(request_id, "Tipo de mensagem desconhecido.")


# ================================================================
# HANDLER WEBSOCKET PRINCIPAL
# ================================================================

async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    ws = AuthenticatedWebSocket(heartbeat=30)
    await ws.prepare(request)

    active_connections: dict[str, AuthenticatedWebSocket] = request.app['active_connections']
    print("Cliente conectado via WebSocket.")

    try:
        async for message in ws:
            if message.type == web.WSMsgType.TEXT:
                try:
                    data: Any = json.loads(message.data)
                    if not isinstance(data, dict):
                        raise ValueError("O formato do payload deve ser um objeto JSON.")

                    message_type: Any = data.get("type")
                    request_id: Any = data.get("requestId")
                    payload: Any = data.get("payload", {})

                    if not isinstance(request_id, str) or not isinstance(message_type, str):
                        raise ValueError("Atributos 'requestId' e 'type' devem ser strings válidas.")

                    await dispatch_message(request.app, ws, request_id, message_type, payload)

                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    await ws.send_error(None, "Formato de mensagem inválido.")

            elif message.type == web.WSMsgType.ERROR:
                print("Erro na conexão WebSocket:", ws.exception())

    finally:
        user_id = ws.get_user_id()
        if ws.is_authenticated and user_id and user_id in active_connections:
            # Garante que a referência removida é exatamente a desta conexão
            if active_connections.get(user_id) == ws:
                del active_connections[user_id]
        
        print(f"Cliente {user_id or 'não-autenticado'} desconectado.")
    
    return ws


# ================================================================
# APP SETUP & INICIALIZAÇÃO
# ================================================================

app: web.Application = web.Application()

# Rota WebSocket
app.router.add_get("/ws", websocket_handler)

# Registra Hooks do Ciclo de Vida do Aplicativo
app.on_startup.append(partial(initialize_database, url=DATABASE_URL))
app.on_cleanup.append(cleanup_database)

if __name__ == "__main__":
    port: int = int(os.environ.get("PORT", "8080"))
    web.run_app(app, host="0.0.0.0", port=port)
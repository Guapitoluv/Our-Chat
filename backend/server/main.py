import os
import json
from functools import partial
from typing import Any, Callable, Awaitable

import asyncpg
from aiohttp import web
from argon2 import PasswordHasher

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
from services.presence_manager import PresenceManager
from initialize_db import initialize_database

# ================================================================
# CONFIGURAÇÕES E VARIÁVEIS DE AMBIENTE
# ================================================================

DATABASE_URL: str | None = os.environ.get("DATABASE_URL")
JWT_SECRET: str | None = os.environ.get("JWT_SECRET")

if not DATABASE_URL:
    raise ValueError(
        "A variável de ambiente DATABASE_URL não foi definida!"
    )

if not JWT_SECRET:
    raise ValueError(
        "A variável de ambiente JWT_SECRET não foi definida!"
    )


# ================================================================
# APLICAÇÃO E SERVIÇOS
# ================================================================

app: web.Application = web.Application()

presence_manager = PresenceManager(app)
app["presence_manager"] = presence_manager

password_hasher = PasswordHasher()


# ================================================================
# INSTÂNCIAS DOS HANDLERS
# ================================================================

send_message_handler = SendMessageHandler(
    presence_manager=presence_manager
)

authentication_handler = AuthenticationHandler(
    presence_manager=presence_manager,
    jwt_secret=JWT_SECRET
)

sign_up_handler = SignUpHandler(
    presence_manager=presence_manager,
    password_hasher=password_hasher,
    jwt_secret=JWT_SECRET
)

sign_in_handler = SignInHandler(
    presence_manager=presence_manager,
    password_hasher=password_hasher,
    jwt_secret=JWT_SECRET
)

get_messages_handler = GetMessagesHandler()
conversation_response_handler = ConversationResponseHandler(
    presence_manager=presence_manager
)
conversation_request_handler = ConversationRequestHandler(
    presence_manager=presence_manager
)
get_conversations_handler = GetConversationsHandler()
get_users_handler = GetUsersHandler()


# ================================================================
# CICLO DE VIDA DO BANCO DE DADOS
# ================================================================

async def cleanup_database(app: web.Application) -> None:
    """Fecha o pool do banco de dados."""

    pool: asyncpg.Pool | None = app.get("db_pool")

    if pool is not None:
        await pool.close()
        print("Pool de conexões com o banco encerrado.")


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
    """Encaminha cada tipo de mensagem ao handler correspondente."""

    handlers: dict[
        str,
        Callable[
            [
                web.Application,
                AuthenticatedWebSocket,
                str,
                dict[str, Any]
            ],
            Awaitable[None]
        ]
    ] = {
        "authenticate": authentication_handler.handle_authenticate,
        "sign_up": sign_up_handler.handle_sign_up,
        "sign_in": sign_in_handler.handle_sign_in,
        "get_users": get_users_handler.handle_get_users,
        "get_conversations":
            get_conversations_handler.handle_get_conversations,
        "get_messages": get_messages_handler.handle_get_messages,
        "conversation_request":
            conversation_request_handler.handle_conversation_request,
        "conversation_response":
            conversation_response_handler.handle_conversation_response,
        "send_message": send_message_handler.handle_send_message,
    }

    handler = handlers.get(message_type)

    if handler is None:
        await ws.send_error(
            request_id,
            "Tipo de mensagem desconhecido."
        )
        return

    await handler(app, ws, request_id, payload)


# ================================================================
# HANDLER PRINCIPAL DO WEBSOCKET
# ================================================================

async def websocket_handler(
    request: web.Request
) -> web.WebSocketResponse:

    ws = AuthenticatedWebSocket(heartbeat=30)
    await ws.prepare(request)

    print("Cliente conectado via WebSocket.")

    try:
        async for message in ws:

            if message.type == web.WSMsgType.TEXT:
                try:
                    data: Any = json.loads(message.data)

                    if not isinstance(data, dict):
                        raise ValueError(
                            "A mensagem deve ser um objeto JSON."
                        )

                    message_type = data.get("type")
                    request_id = data.get("requestId")
                    payload = data.get("payload", {})

                    if (
                        not isinstance(message_type, str)
                        or not isinstance(request_id, str)
                        or not isinstance(payload, dict)
                    ):
                        raise ValueError(
                            "Os campos type, requestId e payload "
                            "possuem formato inválido."
                        )

                    await dispatch_message(
                        request.app,
                        ws,
                        request_id,
                        message_type,
                        payload
                    )

                except (
                    json.JSONDecodeError,
                    ValueError,
                    TypeError
                ):
                    await ws.send_error(
                        None,
                        "Formato de mensagem inválido."
                    )

            elif message.type == web.WSMsgType.ERROR:
                print(
                    "Erro na conexão WebSocket:",
                    ws.exception()
                )

    finally:
        user_id = ws.get_user_id()

        if ws.is_authenticated and user_id:
            try:
                await request.app["presence_manager"].unregister(
                    user_id,
                    ws
                )
            except Exception as exc:
                print(
                    f"Erro ao atualizar presença de "
                    f"{user_id}: {exc}"
                )

        print(
            f"Cliente {user_id or 'não-autenticado'} desconectado."
        )

    return ws


# ================================================================
# ROTAS E CICLO DE VIDA DA APLICAÇÃO
# ================================================================

app.router.add_get("/ws", websocket_handler)

app.on_startup.append(
    partial(initialize_database, url=DATABASE_URL)
)

app.on_cleanup.append(cleanup_database)


# ================================================================
# EXECUÇÃO
# ================================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    web.run_app(app, host="0.0.0.0", port=port)
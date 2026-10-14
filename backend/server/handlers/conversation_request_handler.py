
import uuid
from typing import Any

import asyncpg
from aiohttp import web

from authenticated_websocket import AuthenticatedWebSocket
from services.presence_manager import PresenceManager


class ConversationRequestHandler:
    def __init__(
        self,
        presence_manager: PresenceManager
    ) -> None:
        self.presence_manager = presence_manager

    async def handle_conversation_request(
        self,
        app: web.Application,
        ws: AuthenticatedWebSocket,
        request_id: str,
        payload: dict[str, Any]
    ) -> None:
        # 1. Validação de autenticação
        if not ws.is_authenticated:
            await ws.send_error(request_id, "Não autenticado.")
            return

        current_user_id: str | None = ws.get_user_id()

        if not current_user_id:
            await ws.send_error(
                request_id,
                "Sessão de usuário inválida."
            )
            return

        # 2. Validação dos parâmetros
        recipient_id = payload.get("recipientId")

        if not isinstance(recipient_id, str) or not recipient_id:
            await ws.send_error(
                request_id,
                "recipientId obrigatório."
            )
            return

        if recipient_id == current_user_id:
            await ws.send_error(
                request_id,
                "Não é possível iniciar uma conversa com você mesmo."
            )
            return

        try:
            db_pool: asyncpg.Pool = app["db_pool"]

            async with db_pool.acquire() as conn:
                async with conn.transaction():
                    # 3. Verifica se o destinatário existe
                    recipient_exists = await conn.fetchval(
                        """
                        SELECT EXISTS(
                            SELECT 1
                            FROM users
                            WHERE id = $1
                        )
                        """,
                        recipient_id
                    )

                    if not recipient_exists:
                        await ws.send_error(
                            request_id,
                            "Usuário destinatário não encontrado."
                        )
                        return

                    # 4. Verifica se já existe uma conversa
                    existing_conv = await conn.fetchrow(
                        """
                        SELECT id, requester_id, recipient_id, status
                        FROM conversations
                        WHERE (
                            requester_id = $1
                            AND recipient_id = $2
                        ) OR (
                            requester_id = $2
                            AND recipient_id = $1
                        )
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        current_user_id,
                        recipient_id
                    )

                    if existing_conv:
                        conversation_id = existing_conv["id"]
                        conv_status = existing_conv["status"]
                        requester_id = existing_conv["requester_id"]

                        # Não cria uma solicitação duplicada.
                        is_new_request = False

                    else:
                        conversation_id = str(uuid.uuid4())
                        conv_status = "pending"
                        requester_id = current_user_id
                        is_new_request = True

                        await conn.execute(
                            """
                            INSERT INTO conversations (
                                id,
                                requester_id,
                                recipient_id,
                                status
                            )
                            VALUES ($1, $2, $3, $4)
                            """,
                            conversation_id,
                            current_user_id,
                            recipient_id,
                            conv_status
                        )

            # 5. Resposta para quem solicitou
            await ws.send_json({
                "type": "conversation_request_sent",
                "requestId": request_id,
                "payload": {
                    "conversationId": conversation_id,
                    "status": conv_status,
                    "requesterId": requester_id
                }
            })

            # 6. Notifica o destinatário somente para uma nova solicitação
            if is_new_request:
                recipient_connections = (
                    await self.presence_manager.get_connections(
                        recipient_id
                    )
                )

                notification = {
                    "type": "incoming_conversation_request",
                    "payload": {
                        "conversationId": conversation_id,
                        "requesterId": current_user_id
                    }
                }

                for recipient_ws in recipient_connections:
                    try:
                        await recipient_ws.send_json(notification)
                    except Exception as exc:
                        print(
                            "Erro ao notificar destinatário "
                            f"{recipient_id}: {exc}"
                        )

        except Exception as exc:
            print(
                f"Erro ao processar solicitação de conversa: {exc}"
            )

            await ws.send_error(
                request_id,
                "Erro interno ao criar solicitação de conversa."
            )
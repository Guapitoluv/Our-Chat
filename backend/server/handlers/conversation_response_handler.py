
from typing import Any

import asyncpg
from aiohttp import web

from authenticated_websocket import AuthenticatedWebSocket
from services.presence_manager import PresenceManager


class ConversationResponseHandler:
    def __init__(
        self,
        presence_manager: PresenceManager
    ) -> None:
        self.presence_manager = presence_manager

    async def handle_conversation_response(
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

        # 2. Validação do payload
        conversation_id = payload.get("conversationId")
        accepted = payload.get("accepted")

        if not isinstance(conversation_id, str) or not conversation_id:
            await ws.send_error(
                request_id,
                "conversationId é obrigatório."
            )
            return

        if not isinstance(accepted, bool):
            await ws.send_error(
                request_id,
                "O campo accepted deve ser booleano."
            )
            return

        status_str = "accepted" if accepted else "rejected"

        try:
            db_pool: asyncpg.Pool = app["db_pool"]

            async with db_pool.acquire() as conn:
                # 3. Apenas o destinatário pode responder
                # a uma solicitação que ainda esteja pendente.
                row = await conn.fetchrow(
                    """
                    UPDATE conversations
                    SET
                        status = $1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE
                        id = $2
                        AND recipient_id = $3
                        AND status = 'pending'
                    RETURNING requester_id, recipient_id
                    """,
                    status_str,
                    conversation_id,
                    current_user_id
                )

                if not row:
                    await ws.send_error(
                        request_id,
                        "Solicitação não encontrada, não autorizada "
                        "ou já respondida."
                    )
                    return

                requester_id: str = row["requester_id"]

            # 4. Confirmação para quem respondeu
            await ws.send_json({
                "type": "conversation_response_success",
                "requestId": request_id,
                "payload": {
                    "conversationId": conversation_id,
                    "accepted": accepted
                }
            })

            # 5. Notifica todas as conexões do solicitante
            requester_connections = (
                await self.presence_manager.get_connections(
                    requester_id
                )
            )

            notification = {
                "type": "conversation_status_updated",
                "payload": {
                    "conversationId": conversation_id,
                    "accepted": accepted,
                    "responderId": current_user_id
                }
            }

            for requester_ws in requester_connections:
                try:
                    await requester_ws.send_json(notification)
                except Exception as exc:
                    print(
                        "Erro ao notificar solicitante "
                        f"{requester_id}: {exc}"
                    )

        except Exception as exc:
            print(
                f"Erro ao processar resposta da conversa: {exc}"
            )

            await ws.send_error(
                request_id,
                "Erro interno ao atualizar resposta da conversa."
            )
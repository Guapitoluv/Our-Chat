
import uuid
from typing import Any

import asyncpg
from aiohttp import web

from authentication_websocket import AuthenticatedWebSocket


class SendMessageHandler:
    async def handle_send_message(
        self,
        app: web.Application,
        ws: "AuthenticatedWebSocket",
        request_id: str,
        payload: dict[str, Any]
    ) -> None:
        if not ws.is_authenticated:
            await ws.send_error(
                request_id,
                "Não autenticado."
            )
            return

        user_id = ws.get_user_id()

        if not user_id:
            await ws.send_error(
                request_id,
                "Sessão de usuário inválida."
            )
            return

        conversation_id = payload.get("conversationId")
        message_data = payload.get("message") or {}

        ciphertext = (
            payload.get("ciphertext")
            or message_data.get("ciphertext")
        )
        sender_ciphertext = (
            payload.get("senderCiphertext")
            or message_data.get("senderCiphertext")
        )
        iv = payload.get("iv") or message_data.get("iv")
        sender_iv = (
            payload.get("senderIv")
            or message_data.get("senderIv")
        )

        if (
            not conversation_id
            or not isinstance(ciphertext, str)
            or not isinstance(sender_ciphertext, str)
            or not isinstance(iv, str)
            or not isinstance(sender_iv, str)
        ):
            await ws.send_error(
                request_id,
                "Dados de mensagem incompletos ou inválidos."
            )
            return

        try:
            db_pool: asyncpg.Pool = app["db_pool"]

            async with db_pool.acquire() as conn:
                conv = await conn.fetchrow(
                    """
                    SELECT requester_id, recipient_id, status
                    FROM conversations
                    WHERE id = $1
                      AND (
                          requester_id = $2
                          OR recipient_id = $2
                      )
                    """,
                    conversation_id,
                    user_id
                )

                if not conv:
                    await ws.send_error(
                        request_id,
                        "Conversa não encontrada."
                    )
                    return

                if conv["status"] != "accepted":
                    await ws.send_error(
                        request_id,
                        "Não é possível enviar mensagens para "
                        "uma conversa não aceita."
                    )
                    return

                message_id = str(uuid.uuid4())

                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO messages (
                            id,
                            conversation_id,
                            sender_id,
                            ciphertext,
                            sender_ciphertext,
                            iv,
                            sender_iv
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        message_id,
                        conversation_id,
                        user_id,
                        ciphertext,
                        sender_ciphertext,
                        iv,
                        sender_iv
                    )

                    await conn.execute(
                        """
                        UPDATE conversations
                        SET updated_at = CURRENT_TIMESTAMP
                        WHERE id = $1
                        """,
                        conversation_id
                    )

                target_id = (
                    conv["recipient_id"]
                    if conv["requester_id"] == user_id
                    else conv["requester_id"]
                )

            await ws.send_json({
                "type": "send_message_success",
                "requestId": request_id,
                "payload": {
                    "messageId": message_id,
                    "conversationId": conversation_id
                }
            })

            target_ws = app["active_connections"].get(target_id)

            if target_ws:
                await target_ws.send_json({
                    "type": "new_message",
                    "payload": {
                        "messageId": message_id,
                        "conversationId": conversation_id,
                        "senderId": user_id,
                        "ciphertext": ciphertext,
                        "iv": iv
                    }
                })

        except Exception as e:
            print(
                f"Erro ao salvar mensagem no DB: {e!r}"
            )

            await ws.send_error(
                request_id,
                "Erro interno ao processar e salvar a mensagem."
            )

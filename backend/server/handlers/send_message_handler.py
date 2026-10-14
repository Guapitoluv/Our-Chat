
import uuid
from typing import Any

import asyncpg
from aiohttp import web

from authenticated_websocket import AuthenticatedWebSocket
from services.presence_manager import PresenceManager


class SendMessageHandler:
    def __init__(self, presence_manager: PresenceManager) -> None:
        self.presence_manager = presence_manager

    async def handle_send_message(
        self,
        app: web.Application,
        ws: AuthenticatedWebSocket,
        request_id: str,
        payload: dict[str, Any]
    ) -> None:
        if not ws.is_authenticated:
            await ws.send_error(request_id, "Não autenticado.")
            return

        user_id = ws.get_user_id()
        conversation_id = payload.get("conversationId")
        data = payload.get("message") or {}

        if not user_id:
            await ws.send_error(request_id, "Sessão de usuário inválida.")
            return

        if not isinstance(data, dict):
            await ws.send_error(request_id, "Dados de mensagem inválidos.")
            return

        # ALTERADO: aceita os campos no payload principal ou em message,
        # mantendo compatibilidade com os dois formatos do frontend.
        ciphertext = payload.get("ciphertext") or data.get("ciphertext")
        sender_ciphertext = payload.get("senderCiphertext") or data.get("senderCiphertext")
        iv = payload.get("iv") or data.get("iv")
        sender_iv = payload.get("senderIv") or data.get("senderIv")

        if not isinstance(conversation_id, str) or not conversation_id or not isinstance(ciphertext, str) or not ciphertext or not isinstance(iv, str) or not iv:
            await ws.send_error(request_id, "ID da conversa, ciphertext e IV são obrigatórios.")
            return

        if sender_ciphertext is not None and not isinstance(sender_ciphertext, str):
            await ws.send_error(request_id, "senderCiphertext inválido.")
            return
        if sender_iv is not None and not isinstance(sender_iv, str):
            await ws.send_error(request_id, "senderIv inválido.")
            return

        try:
            async with app["db_pool"].acquire() as conn:
                async with conn.transaction():
                    conv = await conn.fetchrow(
                        """
                        SELECT requester_id, recipient_id
                        FROM conversations
                        WHERE id = $1
                          AND (requester_id = $2 OR recipient_id = $2)
                          AND status = 'accepted'
                        FOR UPDATE
                        """,
                        conversation_id, user_id
                    )

                    if not conv:
                        await ws.send_error(
                            request_id,
                            "Conversa não encontrada, não autorizada ou não aceita."
                        )
                        return

                    message_id = str(uuid.uuid4())
                    await conn.execute(
                        """
                        INSERT INTO messages (
                            id, conversation_id, sender_id, ciphertext,
                            sender_ciphertext, iv, sender_iv
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        message_id, conversation_id, user_id, ciphertext,
                        sender_ciphertext, iv, sender_iv
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

            # ALTERADO: notifica todas as conexões do destinatário,
            # em vez de depender de app["active_connections"].
            notification = {
                "type": "new_message",
                "payload": {
                    "messageId": message_id,
                    "conversationId": conversation_id,
                    "senderId": user_id,
                    "ciphertext": ciphertext,
                    "senderCiphertext": sender_ciphertext,
                    "iv": iv,
                    "senderIv": sender_iv
                }
            }

            for target_ws in await self.presence_manager.get_connections(target_id):
                try:
                    await target_ws.send_json(notification)
                except Exception as exc:
                    print(f"Erro ao notificar {target_id}: {exc}")

        except Exception as exc:
            print(f"Erro ao salvar mensagem no DB: {exc}")
            await ws.send_error(
                request_id,
                "Erro interno ao processar e salvar a mensagem."
            )
import uuid
from typing import Any
import asyncpg
from aiohttp import web

from authenticated_websocket import AuthenticatedWebSocket


class SendMessageHandler:
    def __init__(self) -> None:
        pass

    async def handle_send_message(
        self,
        app: web.Application, 
        ws: AuthenticatedWebSocket, 
        request_id: str, 
        payload: dict[str, Any]
    ) -> None:
        # CORREÇÃO 1: Inversão da checagem de autenticação
        if not ws.is_authenticated:
            await ws.send_error(
                request_id,
                "Não autenticado."
            )
            return

        user_id: str | None = ws.get_user_id()
        if not user_id:
            await ws.send_error(request_id, "Sessão de usuário inválida.")
            return

        conversation_id: str | None = payload.get("conversationId")

        message_data: dict[str, Any] = payload.get("message") or {}
        ciphertext: str | None = payload.get("ciphertext") or message_data.get("ciphertext")
        sender_ciphertext: str | None = payload.get("senderCiphertext") or message_data.get("senderCiphertext")
        iv: str | None = payload.get("iv") or message_data.get("iv")

        if not conversation_id or not ciphertext:
            await ws.send_error(
                request_id,
                "Dados de mensagem incompletos."
            )
            return

        try:
            db_pool: asyncpg.Pool = app['db_pool']
            
            async with db_pool.acquire() as conn:
                # Busca conversa garantindo pertencimento
                conv: asyncpg.Record | None = await conn.fetchrow(
                    """
                    SELECT requester_id, recipient_id, status FROM conversations 
                    WHERE id = $1 AND (requester_id = $2 OR recipient_id = $2)
                    """,
                    conversation_id, user_id
                )

                if not conv:
                    await ws.send_error(
                        request_id,
                        "Conversa não encontrada."
                    )
                    return

                # CORREÇÃO 2: Validação de status da conversa
                if conv["status"] != "accepted":
                    await ws.send_error(
                        request_id,
                        "Não é possível enviar mensagens para uma conversa não aceita."
                    )
                    return

                message_id: str = str(uuid.uuid4())
                
                # Executa inserção da mensagem e atualização da conversa na mesma conexão
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO messages (id, conversation_id, sender_id, ciphertext, sender_ciphertext, iv)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        message_id, conversation_id, user_id, ciphertext, sender_ciphertext, iv
                    )

                    # Atualiza o timestamp da conversa para ordenação
                    await conn.execute(
                        """
                        UPDATE conversations 
                        SET updated_at = CURRENT_TIMESTAMP 
                        WHERE id = $1
                        """,
                        conversation_id
                    )

                target_id: str = (
                    conv["recipient_id"]
                    if conv["requester_id"] == user_id else
                    conv["requester_id"]
                )

            # Resposta de confirmação para o remetente
            await ws.send_json({
                "type": "send_message_success",
                "requestId": request_id,
                "payload": {
                    "messageId": message_id,
                    "conversationId": conversation_id
                }
            })

            # Notificação em tempo real para o destinatário
            active_connections: dict[str, Any] = app['active_connections']
            target_ws: Any = active_connections.get(target_id)
            
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
            print(f"Erro ao salvar mensagem no DB: {str(e)}")
            # Mensagem genérica para segurança do ambiente
            await ws.send_error(
                request_id,
                "Erro interno ao processar e salvar a mensagem."
            )
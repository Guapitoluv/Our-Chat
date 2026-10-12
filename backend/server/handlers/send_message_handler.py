import uuid
from typing import Any

import asyncpg
from aiohttp import web

from authenticated_websocket import AuthenticatedWebSocket


class SendMessageHandler:
    async def handle_send_message(
        self,
        app: web.Application,
        ws: "AuthenticatedWebSocket",
        request_id: str,
        payload: dict[str, Any]
    ) -> None:
        if not ws.is_authenticated:
            await ws.send_error(request_id, "Não autenticado.")
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

        # ALTERAÇÃO: usa o identificador estável enviado pelo cliente.
        # Mensagens de clientes antigos continuam aceitas.
        raw_client_message_id = payload.get("clientMessageId")

        if raw_client_message_id is None:
            client_message_id = str(uuid.uuid4())
        else:
            try:
                client_message_id = str(
                    uuid.UUID(str(raw_client_message_id))
                )
            except (ValueError, TypeError, AttributeError):
                await ws.send_error(
                    request_id,
                    "clientMessageId inválido."
                )
                return
        if (
            not isinstance(conversation_id, str)
            or not conversation_id
            or not isinstance(ciphertext, str)
            or not ciphertext
            or not isinstance(sender_ciphertext, str)
            or not sender_ciphertext
            or not isinstance(iv, str)
            or not iv
            or not isinstance(sender_iv, str)
            or not sender_iv
        ):
            await ws.send_error(
                request_id,
                "Dados de mensagem incompletos ou inválidos."
            )
            return

        try:
            db_pool: asyncpg.Pool = app["db_pool"]
            target_id = None
            inserted = False

            async with db_pool.acquire() as conn:
                async with conn.transaction():
                    conv = await conn.fetchrow(
                        """
                        SELECT requester_id, recipient_id, status
                        FROM conversations
                        WHERE id = $1
                          AND (
                              requester_id = $2
                              OR recipient_id = $2
                          )
                        FOR SHARE
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

                    # ALTERAÇÃO: tenta inserir usando o ID estável.
                    # Se esse ID já existir, não cria outra mensagem.
                    inserted_id = await conn.fetchval(
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
                        ON CONFLICT (id) DO NOTHING
                        RETURNING id
                        """,
                        client_message_id,
                        conversation_id,
                        user_id,
                        ciphertext,
                        sender_ciphertext,
                        iv,
                        sender_iv
                    )

                    inserted = inserted_id is not None

                    # ALTERAÇÃO: se não inseriu, verifica se o ID pertence
                    # à mesma mensagem, usuário e conversa.
                    if not inserted:
                        existing = await conn.fetchrow(
                            """
                            SELECT id, conversation_id, sender_id
                            FROM messages
                            WHERE id = $1
                            """,
                            client_message_id
                        )

                        if (
                            not existing
                            or str(existing["conversation_id"])
                            != str(conversation_id)
                            or str(existing["sender_id"]) != str(user_id)
                        ):
                            await ws.send_error(
                                request_id,
                                "clientMessageId já está em uso."
                            )
                            return

                    # Atualiza a conversa somente quando uma nova mensagem
                    # foi realmente inserida.
                    if inserted:
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
                        if str(conv["requester_id"]) == str(user_id)
                        else conv["requester_id"]
                    )

            # ALTERAÇÃO: tanto uma inserção nova quanto uma repetição
            # válida retornam a mesma confirmação.
            await ws.send_json({
                "type": "send_message_success",
                "requestId": request_id,
                "payload": {
                    "messageId": str(client_message_id),
                    "conversationId": conversation_id,
                    "clientMessageId": str(client_message_id),
                    "duplicate": not inserted
                }
            })

            # ALTERAÇÃO: notifica o destinatário somente na primeira inserção.
            # Uma repetição do envio não gera uma segunda notificação.
            if inserted:
                target_ws = app["active_connections"].get(target_id)

                if target_ws:
                    await target_ws.send_json({
                        "type": "new_message",
                        "payload": {
                            "messageId": str(client_message_id),
                            "conversationId": conversation_id,
                            "senderId": user_id,
                            "ciphertext": ciphertext,
                            "iv": iv
                        }
                    })

        except Exception as e:
            import traceback

            print(
                f"[SendMessageHandler] "
                f"{type(e).__name__}: {e!r}",
                flush=True
            )
            traceback.print_exc()

            await ws.send_error(
                request_id,
                "Erro interno ao processar e salvar a mensagem."
            )

from typing import Any

import asyncpg
from aiohttp import web

from authenticated_websocket import AuthenticatedWebSocket


class GetMessagesHandler:
    def __init__(self) -> None:
        pass

    async def handle_get_messages(
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
        raw_conversation_id = payload.get("conversationId")

        if (
            not isinstance(raw_conversation_id, str)
            or not raw_conversation_id
        ):
            await ws.send_error(
                request_id,
                "conversationId é obrigatório."
            )
            return

        conversation_id: str = raw_conversation_id

        # ALTERADO: valida o tipo antes de converter para int.
        # Isso evita que valores como "abc", listas ou objetos causem erro
        # durante a leitura da paginação.
        raw_limit = payload.get("limit", 50)

        if isinstance(raw_limit, bool):
            await ws.send_error(
                request_id,
                "limit deve ser um número inteiro."
            )
            return

        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            await ws.send_error(
                request_id,
                "limit deve ser um número inteiro."
            )
            return

        # ALTERADO: limita o intervalo permitido para evitar consultas
        # excessivas e impedir que um valor negativo invalide a paginação.
        if limit < 1 or limit > 100:
            await ws.send_error(
                request_id,
                "limit deve estar entre 1 e 100."
            )
            return

        # ALTERADO: before agora deve ser uma string não vazia quando
        # informado. Ele representa o ID da mensagem usada como cursor.
        before = payload.get("before")

        if before is not None and (
            not isinstance(before, str) or not before
        ):
            await ws.send_error(
                request_id,
                "before deve ser um ID de mensagem válido."
            )
            return

        try:
            db_pool: asyncpg.Pool = app["db_pool"]

            async with db_pool.acquire() as conn:
                # 3. Verifica se a conversa existe e se o usuário participa.
                conv = await conn.fetchrow(
                    """
                    SELECT id
                    FROM conversations
                    WHERE id = $1
                      AND (
                          requester_id = $2
                          OR recipient_id = $2
                      )
                    """,
                    conversation_id,
                    current_user_id
                )

                if not conv:
                    await ws.send_error(
                        request_id,
                        "Conversa não encontrada ou não autorizada."
                    )
                    return

                # ALTERADO: busca limit + 1 registros.
                # O registro extra permite determinar se há mais mensagens
                # sem depender da suposição len(messages) == limit.
                if before is not None:
                    rows = await conn.fetch(
                        """
                        SELECT
                            id,
                            conversation_id,
                            sender_id,
                            ciphertext,
                            sender_ciphertext,
                            iv,
                            created_at
                        FROM messages
                        WHERE conversation_id = $1
                          AND created_at < (
                              SELECT created_at
                              FROM messages
                              WHERE id = $2
                                AND conversation_id = $1
                          )
                        ORDER BY created_at DESC, id DESC
                        LIMIT $3
                        """,
                        conversation_id,
                        before,
                        limit + 1
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT
                            id,
                            conversation_id,
                            sender_id,
                            ciphertext,
                            sender_ciphertext,
                            iv,
                            created_at
                        FROM messages
                        WHERE conversation_id = $1
                        ORDER BY created_at DESC, id DESC
                        LIMIT $2
                        """,
                        conversation_id,
                        limit + 1
                    )

                # ALTERADO: hasMore é calculado antes de remover o registro
                # extra. Assim, indica se há mais mensagens anteriores.
                has_more = len(rows) > limit
                rows = rows[:limit]

                # Mantém a ordem cronológica na resposta:
                # da mensagem mais antiga para a mais recente.
                rows = list(reversed(rows))

                messages: list[dict[str, Any]] = []

                for row in rows:
                    messages.append({
                        "id": row["id"],
                        "conversationId": row["conversation_id"],
                        "senderId": row["sender_id"],
                        "ciphertext": row["ciphertext"],
                        "senderCiphertext": row["sender_ciphertext"],
                        "iv": row["iv"],
                        "createdAt": (
                            row["created_at"].isoformat()
                            if row["created_at"] else None
                        )
                    })

            # 4. Resposta para o cliente
            await ws.send_json({
                "type": "get_messages_success",
                "requestId": request_id,
                "payload": {
                    "conversationId": conversation_id,
                    "messages": messages,
                    # ALTERADO: usa o resultado real da consulta limit + 1.
                    "hasMore": has_more
                }
            })

        except Exception as exc:
            print(
                "Erro ao buscar mensagens da conversa "
                f"{conversation_id}: {exc}"
            )

            await ws.send_error(
                request_id,
                "Erro interno ao carregar as mensagens."
            )
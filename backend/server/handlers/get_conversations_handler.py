
from typing import Any

import asyncpg
from aiohttp import web

from ..authenticated_websocket import AuthenticatedWebSocket


class GetConversationsHandler:
    def __init__(self) -> None:
        pass

    async def handle_get_conversations(
        self,
        app: web.Application,
        ws: AuthenticatedWebSocket,
        request_id: str,
        payload: dict[str, Any]
    ) -> None:
        # 1. Validação de autenticação
        if not ws.is_authenticated:
            await ws.send_error(
                request_id,
                "Não autenticado."
            )
            return

        current_user_id: str | None = ws.get_user_id()

        if not current_user_id:
            await ws.send_error(
                request_id,
                "Sessão de usuário inválida."
            )
            return

        try:
            db_pool: asyncpg.Pool = app["db_pool"]

            async with db_pool.acquire() as conn:
                # 2. Busca as conversas e os dados do outro participante.
                rows: list[asyncpg.Record] = await conn.fetch(
                    """
                    SELECT
                        c.id,
                        c.requester_id,
                        c.recipient_id,
                        c.status,
                        c.created_at,
                        c.updated_at,
                        u.id AS other_user_id,
                        u.name AS other_user_name
                    FROM conversations AS c
                    JOIN users AS u
                        ON u.id = CASE
                            WHEN c.requester_id = $1
                                THEN c.recipient_id
                            ELSE c.requester_id
                        END
                    WHERE
                        c.requester_id = $1
                        OR c.recipient_id = $1
                    ORDER BY
                        c.updated_at DESC NULLS LAST,
                        c.created_at DESC
                    """,
                    current_user_id
                )

            # 3. Formata os resultados para o frontend.
            conversations: list[dict[str, Any]] = []

            for row in rows:
                conversations.append({
                    "id": row["id"],
                    "requesterId": row["requester_id"],
                    "recipientId": row["recipient_id"],
                    "otherUser": {
                        "id": row["other_user_id"],
                        "name": row["other_user_name"]
                    },
                    "status": row["status"],
                    "createdAt": (
                        row["created_at"].isoformat()
                        if row["created_at"] else None
                    ),
                    "updatedAt": (
                        row["updated_at"].isoformat()
                        if row["updated_at"] else None
                    )
                })

            # 4. Resposta de sucesso.
            await ws.send_json({
                "type": "get_conversations_success",
                "requestId": request_id,
                "payload": {
                    "conversations": conversations
                }
            })

        except Exception as exc:
            print(
                "Erro ao buscar conversas do usuário "
                f"{current_user_id}: {exc}"
            )

            await ws.send_error(
                request_id,
                "Erro interno ao carregar a lista de conversas."
            )
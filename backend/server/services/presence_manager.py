import logging
from typing import Any

import asyncpg
from aiohttp import web

from authenticated_websocket import AuthenticatedWebSocket
from formatation import format_user_row


logger = logging.getLogger(__name__)


class GetUsersHandler:
    async def handle_get_users(
        self,
        app: web.Application,
        ws: AuthenticatedWebSocket,
        request_id: str,
        payload: dict[str, Any]
    ) -> None:
        if not ws.is_authenticated:
            await ws.send_error(request_id, "Não autenticado.")
            return

        current_user_id = ws.get_user_id()

        if not current_user_id:
            await ws.send_error(
                request_id,
                "Sessão de usuário inválida."
            )
            return

        try:
            db_pool: asyncpg.Pool = app["db_pool"]
            presence_manager = app["presence_manager"]

            async with db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        id,
                        name,
                        email,
                        role,
                        public_key,
                        created_at
                    FROM users
                    WHERE id <> $1
                    ORDER BY name ASC, id ASC
                    """,
                    current_user_id
                )

            users = [format_user_row(row) for row in rows]

            # Extrai os IDs já formatados para consultar a presença.
            user_ids = [str(user["id"]) for user in users]

            statuses = await presence_manager.get_user_status(
                user_ids
            )

            for user in users:
                user["status"] = statuses.get(
                    str(user["id"]),
                    "offline"
                )

            await ws.send_json({
                "type": "get_users_success",
                "requestId": request_id,
                "payload": {
                    "users": users
                }
            })

        except Exception:
            logger.exception(
                "Erro ao buscar usuários: request_id=%s",
                request_id
            )

            await ws.send_error(
                request_id,
                "Erro interno ao carregar os usuários."
            )

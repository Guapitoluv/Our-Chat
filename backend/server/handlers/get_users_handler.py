from typing import Any

import asyncpg
from aiohttp import web

from authenticated_websocket import AuthenticatedWebSocket
from formatation import format_user_row


class GetUsersHandler:
    def __init__(self) -> None:
        pass

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

            async with db_pool.acquire() as conn:
                # Alterado: exclui o usuário atual da lista de contatos
                # e seleciona apenas campos necessários à interface.
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

            # Mantém a conversão de campos e datas centralizada
            # no formatador existente no projeto.
            users = [format_user_row(row) for row in rows]

            await ws.send_json({
                "type": "get_users_success",
                "requestId": request_id,
                "payload": {
                    "users": users
                }
            })

        except Exception as exc:
            print(f"Erro ao buscar usuários: {exc}")

            await ws.send_error(
                request_id,
                "Erro interno ao carregar os usuários."
            )
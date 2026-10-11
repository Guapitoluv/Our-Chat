from typing import Any
import asyncpg
from aiohttp import web

from ..authenticated_websocket import AuthenticatedWebSocket
from ..formatation import format_user_payload


class GetUsersHandler:
    def __init__(self) -> None:
        pass
    
    async def handle_get_users(
        self,  # CORREÇÃO 1: Adicionado 'self'
        app: web.Application,
        ws: AuthenticatedWebSocket,
        request_id: str,
        payload: dict[str, Any]
    ) -> None:
        # 1. Checagem de Autenticação
        if not ws.is_authenticated:
            await ws.send_error(
                request_id,
                "Não autenticado."
            )
            return

        current_user_id: str | None = ws.get_user_id()
        if not current_user_id:
            await ws.send_error(request_id, "Sessão de usuário inválida.")
            return

        # 2. Filtros e limites do payload
        search_term: str = payload.get("query", "").strip()
        limit: int = min(int(payload.get("limit", 20)), 50)  # Máximo de 50 usuários por página

        try:
            db_pool: asyncpg.Pool = app["db_pool"]
            
            async with db_pool.acquire() as conn:
                # 3. Busca com filtro opcional (buscando por nome ou e-mail)
                # exclui o próprio usuário logado do resultado
                if search_term:
                    pattern = f"%{search_term}%"
                    rows: list[asyncpg.Record] = await conn.fetch(
                        """
                        SELECT id, name, email, public_key, role, created_at 
                        FROM users 
                        WHERE id != $1 AND (name ILIKE $2 OR email ILIKE $2)
                        ORDER BY name ASC 
                        LIMIT $3
                        """,
                        current_user_id, pattern, limit
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT id, name, email, public_key, role, created_at 
                        FROM users 
                        WHERE id != $1
                        ORDER BY name ASC 
                        LIMIT $2
                        """,
                        current_user_id, limit
                    )

                users: list[dict[str, Any]] = [format_user_payload(r) for r in rows]
    
            # 4. Resposta para o cliente
            await ws.send_json({
                "type": "get_users_success",
                "requestId": request_id,
                "payload": {"users": users}
            })

        except Exception as e:
            print(f"Erro ao buscar lista de usuários: {e}")
            await ws.send_error(
                request_id,
                "Erro interno ao carregar a lista de usuários."
            )
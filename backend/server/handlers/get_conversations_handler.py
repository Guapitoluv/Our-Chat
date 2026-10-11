from typing import Any
import asyncpg
from aiohttp import web

from ..authenticated_websocket import AuthenticatedWebSocket


class GetConversationsHandler:
    def __init__(self) -> None:
        pass
    
    async def handle_get_conversations(
        self,  # CORREÇÃO 1: Adicionado 'self'
        app: web.Application,
        ws: AuthenticatedWebSocket,
        request_id: str,
        payload: dict[str, Any]
    ) -> None:
        # 1. Validação de Autenticação
        if not ws.is_authenticated:
            await ws.send_error(request_id, "Não autenticado.")
            return

        current_user_id: str | None = ws.get_user_id()
        if not current_user_id:
            await ws.send_error(request_id, "Sessão de usuário inválida.")
            return

        try:
            db_pool: asyncpg.Pool = app['db_pool']

            async with db_pool.acquire() as conn:
                # 2. Busca conversas fazendo JOIN com a tabela users
                # para trazer os dados do outro participante de forma eficiente
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
                        u.name AS other_user_name,
                        u.email AS other_user_email
                    FROM conversations c
                    JOIN users u ON u.id = (
                        CASE 
                            WHEN c.requester_id = $1 THEN c.recipient_id 
                            ELSE c.requester_id 
                        END
                    )
                    WHERE c.requester_id = $1 OR c.recipient_id = $1
                    ORDER BY c.updated_at DESC
                    """,
                    current_user_id
                )
    
            # 3. Formatação dos resultados
            conversations: list[dict[str, Any]] = []
            
            for r in rows:
                conversations.append({
                    "id": r["id"],
                    "requesterId": r["requester_id"],
                    "recipientId": r["recipient_id"],
                    "otherUser": {
                        "id": r["other_user_id"],
                        "name": r["other_user_name"],
                        "email": r["other_user_email"]
                    },
                    "status": r["status"],
                    "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
                    # CORREÇÃO 2: Incluído o updatedAt no retorno
                    "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None
                })
    
            # 4. Resposta de Sucesso
            await ws.send_json({
                "type": "get_conversations_success",
                "requestId": request_id,
                "payload": {"conversations": conversations}
            })

        except Exception as e:
            print(f"Erro ao buscar conversas do usuário {current_user_id}: {e}")
            await ws.send_error(
                request_id,
                "Erro interno ao carregar a lista de conversas."
            )
from typing import Any
import asyncpg
from aiohttp import web

from authenticated_websocket import AuthenticatedWebSocket


class ConversationResponseHandler:
    def __init__(self) -> None:
        pass
    
    async def handle_conversation_response(
        self,  # CORREÇÃO 1: Adicionado 'self'
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
            await ws.send_error(request_id, "Sessão de usuário inválida.")
            return
    
        # 2. Validação do payload
        raw_conversation_id: Any = payload.get("conversationId")
        if not isinstance(raw_conversation_id, str):
            await ws.send_error(request_id, "conversationId é obrigatório.")
            return
        
        conversation_id: str = raw_conversation_id
        accepted: bool = bool(payload.get("accepted"))
        status_str: str = "accepted" if accepted else "rejected"
    
        try:
            db_pool: asyncpg.Pool = app['db_pool']

            async with db_pool.acquire() as conn:
                # CORREÇÃO 2: Garante que APENAS o destinatário (recipient_id) responda
                # e que a conversa esteja no estado 'pending'.
                row: asyncpg.Record | None = await conn.fetchrow(
                    """
                    UPDATE conversations 
                    SET status = $1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = $2 AND recipient_id = $3 AND status = 'pending'
                    RETURNING requester_id, recipient_id
                    """,
                    status_str, conversation_id, current_user_id
                )
    
                if not row:
                    await ws.send_error(
                        request_id,
                        "Solicitação de conversa não encontrada, não autorizada ou já respondida."
                    )
                    return
    
                other_user_id: str = row["requester_id"]

            # 3. Confirmação de sucesso para quem respondeu
            await ws.send_json({
                "type": "conversation_response_success",
                "requestId": request_id,
                "payload": {"conversationId": conversation_id, "accepted": accepted}
            })
            
            # 4. Notificação em tempo real para o criador da solicitação (se online)
            active_connections: dict[str, AuthenticatedWebSocket] = app['active_connections']
            other_ws: AuthenticatedWebSocket | None = active_connections.get(other_user_id)
            
            if other_ws:
                await other_ws.send_json({
                    "type": "conversation_status_updated",
                    "payload": {
                        "conversationId": conversation_id,
                        "accepted": accepted,
                        "responderId": current_user_id
                    }
                })

        except Exception as e:
            print(f"Erro ao processar resposta da conversa: {e}")
            await ws.send_error(
                request_id,
                "Erro interno ao atualizar resposta da conversa."
            )
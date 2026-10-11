import uuid
from typing import Any
import asyncpg
from aiohttp import web

from ..authenticated_websocket import AuthenticatedWebSocket


class ConversationRequestHandler:
    def __init__(self) -> None:
        pass
    
    async def handle_conversation_request(
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

        # 2. Validação dos parâmetros do payload
        recipient_id: str | None = payload.get("recipientId")
        if not recipient_id:
            await ws.send_error(request_id, "recipientId obrigatório.")
            return

        # CORREÇÃO 2: Impede conversa consigo mesmo
        if recipient_id == current_user_id:
            await ws.send_error(
                request_id, 
                "Não é possível iniciar uma conversa com você mesmo."
            )
            return

        try:
            db_pool: asyncpg.Pool = app['db_pool']

            async with db_pool.acquire() as conn:
                # 3. Verifica se o destinatário existe no banco
                recipient_exists: bool = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM users WHERE id = $1)",
                    recipient_id
                )
                if not recipient_exists:
                    await ws.send_error(request_id, "Usuário destinatário não encontrado.")
                    return

                # 4. Verifica se já existe uma conversa ativa ou pendente
                existing_conv: asyncpg.Record | None = await conn.fetchrow(
                    """
                    SELECT id, requester_id, recipient_id, status FROM conversations 
                    WHERE (requester_id = $1 AND recipient_id = $2)
                       OR (requester_id = $2 AND recipient_id = $1)
                    """,
                    current_user_id, recipient_id
                )

                if existing_conv:
                    conversation_id: str = existing_conv["id"]
                    conv_status: str = existing_conv["status"]
                    requester_id: str = existing_conv["requester_id"]
                else:
                    conversation_id = str(uuid.uuid4())
                    conv_status = "pending"
                    requester_id = current_user_id  # CORREÇÃO 3: Padronizado para current_user_id
                    
                    await conn.execute(
                        """
                        INSERT INTO conversations (id, requester_id, recipient_id, status)
                        VALUES ($1, $2, $3, $4)
                        """,
                        conversation_id, current_user_id, recipient_id, conv_status
                    )

            # 5. Resposta para o solicitante
            await ws.send_json({
                "type": "conversation_request_sent",
                "requestId": request_id,
                "payload": {
                    "conversationId": conversation_id,
                    "status": conv_status,
                    "requesterId": requester_id
                }
            })

            # 6. Notificação em tempo real para o destinatário (se online)
            if conv_status == "pending" and requester_id == current_user_id:
                active_connections: dict[str, AuthenticatedWebSocket] = app['active_connections']
                recipient_ws: AuthenticatedWebSocket | None = active_connections.get(recipient_id)
                
                if recipient_ws:
                    await recipient_ws.send_json({
                        "type": "incoming_conversation_request",
                        "payload": {
                            "conversationId": conversation_id,
                            "requesterId": current_user_id
                        }
                    })

        except Exception as e:
            print(f"Erro ao processar solicitação de conversa: {e}")
            await ws.send_error(
                request_id,
                "Erro interno ao criar solicitação de conversa."
            )
from typing import Any
import asyncpg
from aiohttp import web

from authenticated_websocket import AuthenticatedWebSocket


class GetMessagesHandler:
    def __init__(self) -> None:
        pass
    
    async def handle_get_messages(
        self,  # CORREÇÃO 1: Adicionado 'self'
        app: web.Application, 
        ws: AuthenticatedWebSocket, 
        request_id: str, 
        payload: dict[str, Any]
    ) -> None:
        # 1. Validação de Autenticação
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

        # 2. Validação do Payload
        raw_conversation_id: Any = payload.get("conversationId")
        if not isinstance(raw_conversation_id, str):
            await ws.send_error(
                request_id,
                "conversationId é obrigatório."
            )
            return
        
        conversation_id: str = raw_conversation_id
        
        # Parâmetros opcionais para paginação
        limit: int = min(int(payload.get("limit", 50)), 100)  # Máximo de 100 por busca
        before: str | None = payload.get("before")  # ID da mensagem ou ISO timestamp para rolar o histórico

        try:
            db_pool: asyncpg.Pool = app['db_pool']

            async with db_pool.acquire() as conn:
                # 3. Verifica se a conversa existe e se o usuário pertence a ela
                conv: asyncpg.Record | None = await conn.fetchrow(
                    """
                    SELECT id FROM conversations 
                    WHERE id = $1 AND (requester_id = $2 OR recipient_id = $2)
                    """,
                    conversation_id, current_user_id
                )
        
                if not conv:
                    await ws.send_error(
                        request_id,
                        "Conversa não encontrada ou não autorizada."
                    )
                    return
        
                # 4. Busca as mensagens com suporte a paginação
                if before:
                    rows: list[asyncpg.Record] = await conn.fetch(
                        """
                        SELECT
  id,
  conversation_id,
  sender_id,
  ciphertext,
  sender_ciphertext,
  iv,
  sender_iv,
  created_at
                        FROM messages
                        WHERE conversation_id = $1 AND created_at < (
                            SELECT created_at FROM messages WHERE id = $2
                        )
                        ORDER BY created_at DESC
                        LIMIT $3
                        """,
                        conversation_id, before, limit
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
  sender_iv,
  created_at
                        FROM messages
                        WHERE conversation_id = $1
                        ORDER BY created_at DESC
                        LIMIT $2
                        """,
                        conversation_id, limit
                    )
        
                # Inverte para entregar em ordem cronológica (mais antiga -> mais recente)
                rows = list(reversed(rows))

                messages: list[dict[str, Any]] = []
                for r in rows:
                    messages.append({
                        "id": r["id"],
                        "conversationId": r["conversation_id"],
                        "senderId": r["sender_id"],
                        "ciphertext": r["ciphertext"],
                        "senderCiphertext": r["sender_ciphertext"],
                        "iv": r["iv"],
                        "senderIv": r["sender_iv"],
                        "createdAt": r["created_at"].isoformat() if r["created_at"] else None
                    })
        
            # 5. Resposta para o cliente
            await ws.send_json({
                "type": "get_messages_success",
                "requestId": request_id,
                "payload": {
                    "conversationId": conversation_id,
                    "messages": messages,
                    "hasMore": len(messages) == limit
                }
            })

        except Exception as e:
            print(f"Erro ao buscar mensagens da conversa {conversation_id}: {e}")
            await ws.send_error(
                request_id,
                "Erro interno ao carregar as mensagens."
            )

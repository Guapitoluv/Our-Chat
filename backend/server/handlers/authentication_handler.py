from typing import Any
import jwt
from aiohttp import web

from authenticated_websocket import AuthenticatedWebSocket


class AuthenticationHandler:
    def __init__(self, jwt_secret: str) -> None:
        self.jwt_secret = jwt_secret

    async def handle_authenticate(
        self,  # Adicionado 'self'
        app: web.Application, 
        ws: AuthenticatedWebSocket, 
        request_id: str, 
        payload: dict[str, Any]
    ) -> None:
        token: str | None = payload.get("token")

        if not token:
            await ws.send_error(
                request_id,
                "Token de autenticação é obrigatório."
            )
            return

        try:
            # Valida e decodifica o token gerado durante o sign_in
            decoded = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            user_id: str = decoded["user_id"]

            # Atualiza o estado da conexão WebSocket
            ws.set_authenticated(True)
            ws.set_user_id(user_id)

            # Gerencia conexões ativas na aplicação
            active_connections: dict[str, AuthenticatedWebSocket] = app['active_connections']

            # Se o usuário já tiver uma conexão ativa, fecha a antiga antes de substituir
            old_ws = active_connections.get(user_id)
            if old_ws and old_ws != ws:
                await old_ws.close(code=1000, message=b"Nova conexao iniciada")

            active_connections[user_id] = ws

            await ws.send_json({
                "type": "authenticate_success",
                "requestId": request_id,
                "payload": {"status": "authenticated", "userId": user_id}
            })

        except jwt.ExpiredSignatureError:
            await ws.send_error(request_id, "Token expirado.")
        except jwt.InvalidTokenError:
            await ws.send_error(request_id, "Token inválido.")
        except Exception as e:
            print(f"Erro na autenticação WS: {e}")
            await ws.send_error(request_id, "Falha ao autenticar.")
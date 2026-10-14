
from typing import Any

import jwt
from aiohttp import web

from ..authenticated_websocket import AuthenticatedWebSocket
from ..services.presence_manager import PresenceManager


class AuthenticationHandler:
    def __init__(
        self,
        presence_manager: PresenceManager,
        jwt_secret: str
    ) -> None:
        self.presence_manager = presence_manager
        self.jwt_secret = jwt_secret

    async def handle_authenticate(
        self,
        app: web.Application,
        ws: AuthenticatedWebSocket,
        request_id: str,
        payload: dict[str, Any]
    ) -> None:
        token: str | None = payload.get("token")

        if not isinstance(token, str) or not token:
            await ws.send_error(
                request_id,
                "Token de autenticação é obrigatório."
            )
            return

        try:
            decoded = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"]
            )

            user_id = decoded.get("user_id")

            if not isinstance(user_id, str) or not user_id:
                await ws.send_error(
                    request_id,
                    "Token inválido: identificador do usuário ausente."
                )
                return

            # Impede que uma conexão autenticada troque de identidade.
            if ws.is_authenticated:
                current_user_id = ws.get_user_id()

                if current_user_id != user_id:
                    await ws.send_error(
                        request_id,
                        "Esta conexão já está autenticada."
                    )
                    return

                # A mesma identidade já está autenticada.
                await ws.send_json({
                    "type": "authenticate_success",
                    "requestId": request_id,
                    "payload": {
                        "status": "authenticated",
                        "userId": user_id
                    }
                })
                return

            # Registra a conexão no gerenciador de presença.
            await self.presence_manager.register(user_id, ws)

            # Atualiza o estado da conexão após o registro.
            ws.set_user_id(user_id)
            ws.set_authenticated(True)

            await ws.send_json({
                "type": "authenticate_success",
                "requestId": request_id,
                "payload": {
                    "status": "authenticated",
                    "userId": user_id
                }
            })

        except jwt.ExpiredSignatureError:
            await ws.send_error(
                request_id,
                "Token expirado."
            )

        except jwt.InvalidTokenError:
            await ws.send_error(
                request_id,
                "Token inválido."
            )

        except Exception as exc:
            print(f"Erro na autenticação WS: {exc}")

            await ws.send_error(
                request_id,
                "Falha ao autenticar."
            )
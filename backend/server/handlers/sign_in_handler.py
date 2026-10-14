
import asyncio
from typing import Any

import asyncpg
import jwt
from aiohttp import web
from argon2 import PasswordHasher

from authenticated_websocket import AuthenticatedWebSocket
from formatation import format_user_row, format_user_payload
from services.presence_manager import PresenceManager


class SignInHandler:
    def __init__(
        self,
        password_hasher: PasswordHasher,
        jwt_secret: str,
        presence_manager: PresenceManager
    ) -> None:
        self.password_hasher = password_hasher
        self.jwt_secret = jwt_secret
        self.presence_manager = presence_manager

    async def handle_sign_in(
        self,
        app: web.Application,
        ws: AuthenticatedWebSocket,
        request_id: str,
        payload: dict[str, Any]
    ) -> None:
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))

        if not email or not password:
            await ws.send_error(request_id, "E-mail e senha são obrigatórios.")
            return

        try:
            async with app["db_pool"].acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM users WHERE email = $1", email
                )

            if not row:
                await ws.send_error(request_id, "E-mail ou senha incorretos.")
                return

            # Mantido: Argon2 roda em outra thread para não bloquear o Event Loop.
            try:
                await asyncio.to_thread(
                    self.password_hasher.verify, row["password_hash"], password
                )
            except Exception:
                await ws.send_error(request_id, "E-mail ou senha incorretos.")
                return

            user_data = format_user_row(row)
            user_id = user_data["id"]
            token = jwt.encode(
                {"user_id": user_id}, self.jwt_secret, algorithm="HS256"
            )

            # ALTERADO: registra a conexão no PresenceManager em vez de
            # app["active_connections"], removido na nova arquitetura.
            await self.presence_manager.register(user_id, ws)
            ws.set_user_id(user_id)
            ws.set_authenticated(True)

            await ws.send_json({
                "type": "sign_in_success",
                "requestId": request_id,
                "payload": {
                    "token": token,
                    "user": format_user_payload(row),
                    "encryptedBackup": user_data["encrypted_backup"]
                }
            })

        except Exception as exc:
            print(f"Erro no processo de sign_in: {exc}")
            await ws.send_error(
                request_id,
                "Erro interno ao realizar autenticação."
            )
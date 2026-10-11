import asyncio
from typing import Any
import asyncpg
import jwt
from aiohttp import web
from argon2 import PasswordHasher

from authenticated_websocket import AuthenticatedWebSocket
from formatation import format_user_row, format_user_payload


class SignInHandler:
    def __init__(self, password_hasher: PasswordHasher, jwt_secret: str) -> None:
        self.password_hasher = password_hasher
        self.jwt_secret = jwt_secret

    async def handle_sign_in(
        self,  # CORREÇÃO 1: Adicionado 'self'
        app: web.Application, 
        ws: AuthenticatedWebSocket, 
        request_id: str, 
        payload: dict[str, Any]
    ) -> None:
        email: str = str(payload.get("email", "")).strip().lower()
        password: str = str(payload.get("password", ""))

        if not email or not password:
            await ws.send_error(
                request_id,
                "E-mail e senha são obrigatórios."
            )
            return

        try:
            db_pool: asyncpg.Pool = app['db_pool']

            async with db_pool.acquire() as conn:
                row: asyncpg.Record | None = await conn.fetchrow(
                    "SELECT * FROM users WHERE email = $1", 
                    email
                )
                
                if not row:
                    await ws.send_error(
                        request_id,
                        "E-mail ou senha incorretos."
                    )
                    return

                # CORREÇÃO 2: Executa o Argon2 em uma thread separada para NÃO bloquear o Event Loop
                try:
                    await asyncio.to_thread(
                        self.password_hasher.verify, 
                        row["password_hash"], 
                        password
                    )
                except Exception:
                    await ws.send_error(
                        request_id,
                        "E-mail ou senha incorretos."
                    )
                    return

                user_data: dict[str, Any] = format_user_row(row)
                user_id: str = user_data["id"]

                # CORREÇÃO 3: Gera o token JWT para autenticações futuras
                token = jwt.encode(
                    {"user_id": user_id}, 
                    self.jwt_secret, 
                    algorithm="HS256"
                )

                # Define o usuário na conexão atual e registra em conexões ativas
                ws.set_authenticated(True)
                ws.set_user_id(user_id)
                app['active_connections'][user_id] = ws

                # Envia confirmação contendo o token JWT
                await ws.send_json({
                    "type": "sign_in_success",
                    "requestId": request_id,
                    "payload": {
                        "token": token,
                        "user": format_user_payload(row),
                        "encryptedBackup": user_data["encrypted_backup"]
                    }
                })

        except Exception as e:
            print(f"Erro no processo de sign_in: {e}")
            await ws.send_error(
                request_id,
                "Erro interno ao realizar autenticação."
            )

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
        # ALTERADO: registra o início do método e força a saída imediata.
        print("[SIGN_IN] Método iniciado", flush=True)

        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))

        if not email or not password:
            print("[SIGN_IN] Credenciais ausentes", flush=True)
            await ws.send_error(
                request_id,
                "E-mail e senha são obrigatórios."
            )
            return

        try:
            # ALTERADO: identifica se a execução chega à consulta SQL.
            print("[SIGN_IN] Consultando banco", flush=True)

            async with app["db_pool"].acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM users WHERE email = $1",
                    email
                )

            print("[SIGN_IN] Consulta concluída", flush=True)

            if not row:
                print("[SIGN_IN] Usuário não encontrado", flush=True)
                await ws.send_error(
                    request_id,
                    "E-mail ou senha incorretos."
                )
                return

            # ALTERADO: identifica o início da verificação da senha.
            print("[SIGN_IN] Verificando senha", flush=True)

            try:
                await asyncio.to_thread(
                    self.password_hasher.verify,
                    row["password_hash"],
                    password
                )
            except Exception as exc:
                # ALTERADO: registra o tipo do erro sem expor a senha.
                print(
                    f"[SIGN_IN] Falha na verificação: "
                    f"{type(exc).__name__}",
                    flush=True
                )
                await ws.send_error(
                    request_id,
                    "E-mail ou senha incorretos."
                )
                return

            user_data = format_user_row(row)
            user_id = user_data["id"]

            token = jwt.encode(
                {"user_id": user_id},
                self.jwt_secret,
                algorithm="HS256"
            )

            # ALTERADO: verifica se o registro de presença é alcançado.
            print(
                "[SIGN_IN] Antes de registrar presença",
                flush=True
            )

            await self.presence_manager.register(user_id, ws)

            # ALTERADO: só aparece se register() terminar com sucesso.
            print(
                "[SIGN_IN] Presença registrada",
                flush=True
            )

            ws.set_user_id(user_id)

            await ws.send_json({
                "type": "sign_in_success",
                "requestId": request_id,
                "payload": {
                    "token": token,
                    "user": format_user_payload(row),
                    "encryptedBackup": user_data["encrypted_backup"]
                }
            })

            print("[SIGN_IN] Resposta enviada", flush=True)

        except Exception as exc:
            # ALTERADO: inclui o tipo da exceção para facilitar o diagnóstico.
            print(
                f"[SIGN_IN] Erro: {type(exc).__name__}: {exc}",
                flush=True
            )

            # Mantém o fluxo original de resposta de erro.
            # Em produção, não exponha detalhes internos da exceção ao cliente.
            await ws.send_error(
                request_id,
                "Erro interno ao realizar autenticação."
            )

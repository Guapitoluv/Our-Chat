
import asyncio
import json
import uuid
from typing import Any

import asyncpg
import jwt
from aiohttp import web
from argon2 import PasswordHasher

from ..authenticated_websocket import AuthenticatedWebSocket
from ..formatation import format_user_payload
from ..services.presence_manager import PresenceManager


class SignUpHandler:
    def __init__(
        self,
        password_hasher: PasswordHasher,
        jwt_secret: str,
        presence_manager: PresenceManager
    ) -> None:
        self.password_hasher = password_hasher
        self.jwt_secret = jwt_secret
        self.presence_manager = presence_manager

    async def handle_sign_up(
        self,
        app: web.Application,
        ws: AuthenticatedWebSocket,
        request_id: str,
        payload: dict[str, Any]
    ) -> None:
        name, email, password = (
            payload.get("name"), payload.get("email"), payload.get("password")
        )
        public_key = payload.get("publicKey")
        encrypted_backup = payload.get("encryptedBackup")

        if not all(isinstance(v, str) for v in (name, email, password)):
            await ws.send_error(
                request_id, "Nome, e-mail e senha devem ser textos válidos."
            )
            return

        if not name.strip() or not email.strip() or not password:
            await ws.send_error(
                request_id, "Campos obrigatórios não podem ser vazios."
            )
            return

        # ALTERADO: exige estruturas criptográficas presentes e serializáveis
        # em JSON, para evitar gravar valores inválidos nas colunas JSONB.
        if public_key is None or encrypted_backup is None:
            await ws.send_error(request_id, "Chaves criptográficas ausentes.")
            return

        try:
            public_key_json = json.dumps(public_key)
            backup_json = json.dumps(encrypted_backup)
            password_hash = await asyncio.to_thread(
                self.password_hasher.hash, password
            )
            user_id = str(uuid.uuid4())

            async with app["db_pool"].acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO users (
                        id, name, email, password_hash,
                        public_key, encrypted_backup
                    )
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
                    RETURNING id, name, email, role, public_key, created_at
                    """,
                    user_id, name.strip(), email.strip().lower(),
                    password_hash, public_key_json, backup_json
                )

            token = jwt.encode(
                {"user_id": user_id}, self.jwt_secret, algorithm="HS256"
            )

            # ALTERADO: registra a sessão no PresenceManager, substituindo
            # app["active_connections"], que não faz mais parte do main.py.
            await self.presence_manager.register(user_id, ws)
            ws.set_user_id(user_id)
            ws.set_authenticated(True)

            await ws.send_json({
                "type": "sign_up_success",
                "requestId": request_id,
                "payload": {
                    "token": token,
                    "user": format_user_payload(row)
                }
            })

        except asyncpg.UniqueViolationError:
            await ws.send_error(request_id, "E-mail já cadastrado.")
        except (TypeError, ValueError) as exc:
            # ALTERADO: diferencia dados criptográficos não serializáveis
            # de falhas inesperadas no banco ou no servidor.
            print(f"Dados criptográficos inválidos: {exc}")
            await ws.send_error(request_id, "Dados criptográficos inválidos.")
        except Exception as exc:
            print(f"Erro no cadastro de usuário: {exc}")
            await ws.send_error(
                request_id, "Erro interno ao realizar cadastro."
            )
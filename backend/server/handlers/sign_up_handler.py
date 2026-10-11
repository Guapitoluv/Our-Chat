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


class SignUpHandler:
    def __init__(self, password_hasher: PasswordHasher, jwt_secret: str) -> None:
        self.password_hasher = password_hasher
        self.jwt_secret = jwt_secret

    async def handle_sign_up(
        self,  # CORREÇÃO 1: Adicionado 'self'
        app: web.Application, 
        ws: AuthenticatedWebSocket, 
        request_id: str, 
        payload: dict[str, Any]
    ) -> None:
        raw_name: Any = payload.get("name")
        raw_email: Any = payload.get("email")
        raw_password: Any = payload.get("password")
        raw_public_key: Any = payload.get("publicKey")
        raw_encrypted_backup: Any = payload.get("encryptedBackup")
        
        # CORREÇÃO 2: Sintaxe corrigida do list comprehension
        if not all(isinstance(x, str) for x in [raw_name, raw_email, raw_password]):
            await ws.send_error(
                request_id,
                "Nome, e-mail e senha devem ser textos válidos."
            )
            return
        
        # CORREÇÃO 3: Adicionado 'return' que faltava
        if not raw_public_key or not raw_encrypted_backup:
            await ws.send_error(request_id, "Chaves criptográficas ausentes.")
            return
        
        clean_name: str = raw_name.strip()
        clean_email: str = raw_email.strip().lower()

        if not clean_name or not clean_email or not raw_password:
            await ws.send_error(request_id, "Campos obrigatórios não podem ser vazios.")
            return

        try:
            # CORREÇÃO 4: Executa o Hashing em thread separada para não travar o Event Loop
            password_hash: str = await asyncio.to_thread(
                self.password_hasher.hash, 
                raw_password
            )

            # Serializa para JSON mantendo compatibilidade com a coluna JSONB do asyncpg
            public_key_json: str = json.dumps(raw_public_key) if not isinstance(raw_public_key, str) else raw_public_key
            encrypted_backup_json: str = json.dumps(raw_encrypted_backup) if not isinstance(raw_encrypted_backup, str) else raw_encrypted_backup

            user_id: str = str(uuid.uuid4())
            db_pool: asyncpg.Pool = app['db_pool']

            async with db_pool.acquire() as conn:
                row: asyncpg.Record = await conn.fetchrow(
                    """
                    INSERT INTO users (id, name, email, password_hash, public_key, encrypted_backup)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
                    RETURNING id, name, email, role, public_key, created_at
                    """,
                    user_id, clean_name, clean_email, password_hash,
                    public_key_json, encrypted_backup_json
                )

            # CORREÇÃO 5: Geração do Token JWT
            token: str = jwt.encode(
                {"user_id": user_id}, 
                self.jwt_secret, 
                algorithm="HS256"
            )

            # Atualiza a sessão e a lista de conexões ativas
            ws.set_authenticated(True)
            ws.set_user_id(user_id)
            app['active_connections'][user_id] = ws

            # Retorna o sucesso acompanhado do Token JWT
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
        except Exception as e:
            print(f"Erro no cadastro de usuário: {e}")
            await ws.send_error(
                request_id,
                "Erro interno ao realizar cadastro."
            )

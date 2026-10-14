
import json
from typing import Any

import asyncpg


def format_user_row(row: asyncpg.Record) -> dict[str, Any]:
    user: dict[str, Any] = dict(row)

    if user.get("created_at"):
        user["created_at"] = user["created_at"].isoformat()

    # ALTERADO: converte JSON textual para objetos Python quando necessário.
    for field in ("public_key", "encrypted_backup"):
        if isinstance(user.get(field), str):
            user[field] = json.loads(user[field])

    return user


def format_user_payload(user_row: asyncpg.Record) -> dict[str, Any]:
    user_data = format_user_row(user_row)

    # ALTERADO: não expõe o backup criptografado nas respostas comuns.
    return {
        "id": user_data["id"],
        "name": user_data["name"],
        "email": user_data["email"],
        "role": user_data.get("role", "user"),
        "publicKey": user_data.get("public_key"),
        "createdAt": user_data.get("created_at")
    }
from typing import Any

import asyncpg


def format_user_row(row: asyncpg.Record) -> dict[str, Any]:
    user: dict[str, Any] = dict(row)
    if user.get("created_at"):
        user["created_at"] = user["created_at"].isoformat()
    if isinstance(user.get("public_key"), str):
        user["public_key"] = json.loads(user["public_key"])
    if isinstance(user.get("encrypted_backup"), str):
        user["encrypted_backup"] = json.loads(user["encrypted_backup"])
    return user


def format_user_payload(user_row: asyncpg.Record) -> dict[str, Any]:
    user_data: dict[str, Any] = format_user_row(user_row)
    return {
        "id": user_data["id"],
        "name": user_data["name"],
        "email": user_data["email"],
        "role": user_data.get("role", "user"),
        "publicKey": user_data.get("public_key"),
        "createdAt": user_data.get("created_at")
    }
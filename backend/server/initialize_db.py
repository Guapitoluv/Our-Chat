import os
import asyncpg
from aiohttp import web


async def initialize_database(
    app: web.Application,
    url: str
) -> None:
    """Inicializa o pool e cria as tabelas necessárias."""

    print("Conectando ao banco de dados Supabase...")

    pool = await asyncpg.create_pool(
        url,
        min_size=1,
        max_size=5,
        statement_cache_size=0
    )

    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    public_key JSONB NOT NULL,
                    encrypted_backup JSONB NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at TIMESTAMP WITH TIME ZONE
                        DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    requester_id TEXT NOT NULL
                        REFERENCES users(id),
                    recipient_id TEXT NOT NULL
                        REFERENCES users(id),
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP WITH TIME ZONE
                        DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE
                        DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL
                        REFERENCES conversations(id),
                    sender_id TEXT NOT NULL
                        REFERENCES users(id),
                    ciphertext TEXT NOT NULL,
                    sender_ciphertext TEXT,
                    iv TEXT,
                    created_at TIMESTAMP WITH TIME ZONE
                        DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_conversations_users
                ON conversations(requester_id, recipient_id);
            """)

        app["db_pool"] = pool

        print("Banco de dados e tabelas prontos para uso!")

    except Exception:
        await pool.close()
        raise

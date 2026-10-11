import os
import asyncpg
from aiohttp import web


async def initialize_database(app: web.Application) -> None:
    """Inicializa o pool de conexões e cria as tabelas necessárias no Supabase."""
    database_url = os.environ.get("DATABASE_URL")
    
    if not database_url:
        raise ValueError("A variável de ambiente DATABASE_URL não foi definida!")

    print("Conectando ao banco de dados Supabase...")

    # Criação do pool adaptado para PgBouncer/Supabase
    pool = await asyncpg.create_pool(
        database_url,
        min_size=1,
        max_size=5,
        statement_cache_size=0
    )
    
    app['db_pool'] = pool
    app['active_connections'] = {}

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
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    requester_id TEXT NOT NULL REFERENCES users(id),
                    recipient_id TEXT NOT NULL REFERENCES users(id),
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id),
                    sender_id TEXT NOT NULL REFERENCES users(id),
                    ciphertext TEXT NOT NULL,
                    sender_ciphertext TEXT,
                    iv TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );

                -- Índices para otimizar busca de conversas e mensagens
                CREATE INDEX IF NOT EXISTS idx_messages_conversation_id 
                ON messages(conversation_id, created_at DESC);
                
                CREATE INDEX IF NOT EXISTS idx_conversations_participants 
                ON conversations(requester_id, recipient_id);
            """)
        print("Banco de dados e tabelas prontos para uso!")
    
    except Exception as e:
        print(f"Erro ao inicializar o banco de dados: {e}")
        await pool.close()
        raise e
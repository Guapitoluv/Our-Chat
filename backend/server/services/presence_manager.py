import asyncio
from typing import Any

from authenticated_websocket import AuthenticatedWebSocket


class PresenceManager:
    ONLINE_STATUS: str = "online"
    OFFLINE_STATUS: str = "offline"

    def __init__(self, app) -> None:
        self.active_connections: dict[
            str, set[AuthenticatedWebSocket]
        ] = {}
        
        self.app = app
        self._lock = asyncio.Lock()

    async def register(
        self,
        user_id: str,
        ws: AuthenticatedWebSocket
    ) -> None:
        print(f"registering: {user_id}")
        
        async with self._lock:
            print("start async with self._lock")
            connections: set[
                AuthenticatedWebSocket
            ] = self.active_connections.setdefault(
                user_id, set()
            )

            was_online: bool = bool(connections)
            connections.add(ws)

            should_broadcast: bool = not was_online
            print("end async with self._lock")
        
        print(f"should broadcast: {should_broadcast}")
        if should_broadcast:
            await self.broadcast_presence(
                user_id,
                self.ONLINE_STATUS
            )

    async def unregister(
        self,
        user_id: str,
        ws: AuthenticatedWebSocket
    ) -> None:
        async with self._lock:
            connections: set[
                AuthenticatedWebSocket
            ] = self.active_connections.get(user_id)

            if not connections:
                return

            # Remove somente esta conexão.
            connections.discard(ws)

            # Ainda há outras conexões do usuário.
            if connections:
                return

            # Nenhuma conexão restante: usuário offline.
            del self.active_connections[user_id]

        await self.broadcast_presence(
            user_id,
            self.OFFLINE_STATUS
        )

    async def broadcast_presence(
        self,
        user_id: str,
        user_status: str
    ) -> None:
        print(f"broadcasting presence: {user_id}, {user_status}")
        contact_ids: list[
            str
        ] = await self._get_contact_ids(user_id)

        message: dict[str, Any] = {
            "type": "presence_update",
            "payload": {
                "userId": user_id,
                "status": user_status
            }
        }

        # Envia somente aos contatos conectados.
        for contact_id in contact_ids:
            connections: set[
                AuthenticatedWebSocket
            ] = self.active_connections.get(contact_id)

            if not connections:
                continue

            for contact_ws in tuple(connections):
                try:
                    await contact_ws.send_json(message)
                except Exception as exc:
                    print(
                        f"Erro ao enviar presença para "
                        f"{contact_id}: {exc}"
                    )
        
        print(f"end of broadcast: ids={contact_ids}")

    async def _get_contact_ids(self, user_id: str) -> list[str]:
        async with self.app["db_pool"].acquire() as conn:
            rows = await conn.fetch(
                "SELECT id FROM users WHERE id != $1",
                user_id
            )
    
        return [row["id"] for row in rows]
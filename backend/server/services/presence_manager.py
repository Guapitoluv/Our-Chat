import asyncio
from typing import Any

from ..authenticated_websocket import AuthenticatedWebSocket


class PresenceManager:
    ONLINE_STATUS = "online"
    OFFLINE_STATUS = "offline"

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
        user_id = str(user_id)

        async with self._lock:
            connections = self.active_connections.setdefault(
                user_id, set()
            )

            was_online = bool(connections)
            connections.add(ws)

            should_broadcast = not was_online

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
        user_id = str(user_id)

        async with self._lock:
            connections = self.active_connections.get(user_id)

            if not connections:
                return

            connections.discard(ws)

            if connections:
                return

            del self.active_connections[user_id]

        await self.broadcast_presence(
            user_id,
            self.OFFLINE_STATUS
        )

    async def get_user_status(
        self,
        user_ids: list[str]
    ) -> dict[str, str]:
        # Lê um snapshot consistente das conexões registradas.
        async with self._lock:
            return {
                str(user_id): (
                    self.ONLINE_STATUS
                    if self.active_connections.get(str(user_id))
                    else self.OFFLINE_STATUS
                )
                for user_id in user_ids
            }

    async def broadcast_presence(
        self,
        user_id: str,
        user_status: str
    ) -> None:
        contact_ids = await self._get_contact_ids(user_id)

        message: dict[str, Any] = {
            "type": "presence_update",
            "payload": {
                "userId": str(user_id),
                "status": user_status
            }
        }

        for contact_id in contact_ids:
            # Não mantém o lock durante o envio pela rede.
            async with self._lock:
                connections = tuple(
                    self.active_connections.get(str(contact_id), ())
                )

            for contact_ws in connections:
                try:
                    await contact_ws.send_json(message)
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception(
                        "Falha ao enviar presença: destinatário=%s",
                        contact_id
                    )

    async def _get_contact_ids(
        self,
        user_id: str
    ) -> list[str]:
        async with self.app["db_pool"].acquire() as conn:
            rows = await conn.fetch(
                "SELECT id FROM users WHERE id != $1",
                user_id
            )

        return [str(row["id"]) for row in rows]

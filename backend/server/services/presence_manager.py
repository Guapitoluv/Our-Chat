import asyncio
import logging
from typing import Any

from authenticated_websocket import AuthenticatedWebSocket


logger = logging.getLogger(__name__)


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
        logger.debug(
            "[PRESENCE][REGISTER] Iniciando registro: user_id=%s",
            user_id
        )

        async with self._lock:
            connections = self.active_connections.setdefault(
                user_id, set()
            )

            was_online = bool(connections)
            connections.add(ws)

            connection_count = len(connections)
            should_broadcast = not was_online

        logger.info(
            "[PRESENCE][REGISTER] Registro concluído: "
            "user_id=%s, conexões=%d, já_estava_online=%s",
            user_id,
            connection_count,
            was_online
        )

        if should_broadcast:
            logger.debug(
                "[PRESENCE][REGISTER] Primeira conexão; "
                "publicando presença online: user_id=%s",
                user_id
            )

            await self.broadcast_presence(
                user_id,
                self.ONLINE_STATUS
            )
        else:
            logger.debug(
                "[PRESENCE][REGISTER] Usuário já estava online; "
                "broadcast dispensado: user_id=%s",
                user_id
            )

    async def unregister(
        self,
        user_id: str,
        ws: AuthenticatedWebSocket
    ) -> None:
        logger.debug(
            "[PRESENCE][UNREGISTER] Iniciando remoção: user_id=%s",
            user_id
        )

        async with self._lock:
            connections = self.active_connections.get(user_id)

            if not connections:
                logger.warning(
                    "[PRESENCE][UNREGISTER] Usuário sem conexões "
                    "registradas: user_id=%s",
                    user_id
                )
                return

            if ws not in connections:
                logger.warning(
                    "[PRESENCE][UNREGISTER] WebSocket não registrado: "
                    "user_id=%s, conexões=%d",
                    user_id,
                    len(connections)
                )
                return

            connections.remove(ws)
            connection_count = len(connections)

            if connections:
                logger.info(
                    "[PRESENCE][UNREGISTER] Conexão removida; "
                    "usuário continua online: user_id=%s, conexões=%d",
                    user_id,
                    connection_count
                )
                return

            del self.active_connections[user_id]

        logger.info(
            "[PRESENCE][UNREGISTER] Última conexão removida; "
            "usuário ficou offline: user_id=%s",
            user_id
        )

        await self.broadcast_presence(
            user_id,
            self.OFFLINE_STATUS
        )

    async def broadcast_presence(
        self,
        user_id: str,
        user_status: str
    ) -> None:
        logger.info(
            "[PRESENCE][BROADCAST] Iniciando: user_id=%s, status=%s",
            user_id,
            user_status
        )

        try:
            contact_ids = await self._get_contact_ids(user_id)
        except Exception:
            logger.exception(
                "[PRESENCE][BROADCAST] Falha ao consultar contatos: "
                "user_id=%s, status=%s",
                user_id,
                user_status
            )
            return

        message: dict[str, Any] = {
            "type": "presence_update",
            "payload": {
                "userId": user_id,
                "status": user_status
            }
        }

        attempted = 0
        succeeded = 0
        failed = 0
        skipped = 0

        logger.debug(
            "[PRESENCE][BROADCAST] Contatos encontrados: "
            "user_id=%s, quantidade=%d",
            user_id,
            len(contact_ids)
        )

        for contact_id in contact_ids:
            # Obtém uma fotografia consistente das conexões.
            async with self._lock:
                connections = tuple(
                    self.active_connections.get(contact_id, ())
                )

            if not connections:
                skipped += 1

                logger.debug(
                    "[PRESENCE][BROADCAST] Contato sem conexões "
                    "ativas: contact_id=%s",
                    contact_id
                )
                continue

            for contact_ws in connections:
                attempted += 1

                try:
                    await contact_ws.send_json(message)
                    succeeded += 1

                    logger.debug(
                        "[PRESENCE][BROADCAST] Envio concluído: "
                        "destinatário=%s, origem=%s, status=%s",
                        contact_id,
                        user_id,
                        user_status
                    )

                except Exception:
                    failed += 1

                    logger.exception(
                        "[PRESENCE][BROADCAST] Falha no envio: "
                        "destinatário=%s, origem=%s, status=%s",
                        contact_id,
                        user_id,
                        user_status
                    )

        logger.info(
            "[PRESENCE][BROADCAST] Concluído: "
            "origem=%s, status=%s, contatos=%d, "
            "tentativas=%d, enviados=%d, falhas=%d, "
            "contatos_sem_conexão=%d",
            user_id,
            user_status,
            len(contact_ids),
            attempted,
            succeeded,
            failed,
            skipped
        )

    async def _get_contact_ids(
        self,
        user_id: str
    ) -> list[str]:
        logger.debug(
            "[PRESENCE][DATABASE] Consultando contatos: user_id=%s",
            user_id
        )

        try:
            async with self.app["db_pool"].acquire() as conn:
                rows = await conn.fetch(
                    "SELECT id FROM users WHERE id != $1",
                    user_id
                )

            contact_ids = [str(row["id"]) for row in rows]

            logger.debug(
                "[PRESENCE][DATABASE] Consulta concluída: "
                "user_id=%s, quantidade=%d",
                user_id,
                len(contact_ids)
            )

            return contact_ids

        except Exception:
            logger.exception(
                "[PRESENCE][DATABASE] Erro ao consultar contatos: "
                "user_id=%s",
                user_id
            )
            raise

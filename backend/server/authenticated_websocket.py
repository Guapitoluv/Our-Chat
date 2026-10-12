from aiohttp import web
from typing import Any


# Subclasse customizada para reconhecer a propriedade dinâmica 'user_id' nos Mypy/Linters
class AuthenticatedWebSocket(web.WebSocketResponse):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._user_id: str | None = None  # Convenção '_' indica atributo privado da instância

    def set_user_id(self, user_id: str) -> None:
        """Define e vincula o ID do usuário autenticado à conexão WebSocket."""
        if not user_id:
            raise ValueError("O user_id não pode ser vazio.")
        self._user_id = user_id

    def get_user_id(self) -> str | None:
        """Retorna o ID do usuário vinculado à sessão atual ou None."""
        return self._user_id

    @property
    def is_authenticated(self) -> bool:
        """Propriedade auxiliar para checar rapidamente se a conexão está autenticada."""
        return self._user_id is not None
    
    async def send_error(self, request_id: str | None, message: str) -> None:
        await self.send_json({
            "type": "error",
            "requestId": request_id,
            "payload": {"message": message}
        })
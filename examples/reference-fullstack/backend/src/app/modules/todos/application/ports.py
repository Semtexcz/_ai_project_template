from typing import Protocol

from app.modules.todos.domain.model import Todo


class TodoRepository(Protocol):
    def list(self) -> list[Todo]: ...

    def add(self, todo: Todo) -> None: ...

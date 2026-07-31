from app.modules.todos.domain.model import Todo


class InMemoryTodoRepository:
    def __init__(self) -> None:
        self._items: list[Todo] = []

    def list(self) -> list[Todo]:
        return list(self._items)

    def add(self, todo: Todo) -> None:
        self._items.append(todo)

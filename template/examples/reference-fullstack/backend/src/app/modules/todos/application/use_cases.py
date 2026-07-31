from app.modules.todos.application.ports import TodoRepository
from app.modules.todos.domain.model import Todo


class ListTodos:
    def __init__(self, repository: TodoRepository) -> None:
        self._repository = repository

    def execute(self) -> list[Todo]:
        return self._repository.list()


class CreateTodo:
    def __init__(self, repository: TodoRepository) -> None:
        self._repository = repository

    def execute(self, title: str) -> Todo:
        todo = Todo(id="generated-id", title=title).rename(title)
        self._repository.add(todo)
        return todo

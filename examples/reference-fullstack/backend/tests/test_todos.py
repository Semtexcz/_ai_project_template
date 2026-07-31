import pytest

from app.modules.todos.application.use_cases import CreateTodo, ListTodos
from app.modules.todos.infrastructure.repository import InMemoryTodoRepository


def test_create_and_list_todos() -> None:
    repository = InMemoryTodoRepository()

    created = CreateTodo(repository).execute(" Ship slice ")

    assert created.title == "Ship slice"
    assert ListTodos(repository).execute() == [created]


def test_empty_title_is_rejected() -> None:
    repository = InMemoryTodoRepository()

    with pytest.raises(ValueError):
        CreateTodo(repository).execute(" ")

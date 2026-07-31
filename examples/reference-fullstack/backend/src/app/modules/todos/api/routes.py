from fastapi import APIRouter
from pydantic import BaseModel

from app.modules.todos.application.use_cases import CreateTodo, ListTodos
from app.modules.todos.infrastructure.repository import InMemoryTodoRepository


class TodoCreateRequest(BaseModel):
    title: str


class TodoResponse(BaseModel):
    id: str
    title: str
    completed: bool


router = APIRouter(prefix="/todos", tags=["todos"])
repository = InMemoryTodoRepository()


@router.get("", response_model=list[TodoResponse])
def list_todos() -> list[TodoResponse]:
    return [TodoResponse(**todo.__dict__) for todo in ListTodos(repository).execute()]


@router.post("", response_model=TodoResponse, status_code=201)
def create_todo(request: TodoCreateRequest) -> TodoResponse:
    todo = CreateTodo(repository).execute(request.title)
    return TodoResponse(**todo.__dict__)

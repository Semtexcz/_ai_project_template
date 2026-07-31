from fastapi import APIRouter
from pydantic import BaseModel

from app.modules.example.application.use_cases import GetExampleMessage


class ExampleResponse(BaseModel):
    message: str


router = APIRouter(prefix="/example", tags=["example"])


@router.get("", response_model=ExampleResponse)
def get_example() -> ExampleResponse:
    message = GetExampleMessage().execute()
    return ExampleResponse(message=message.normalized())

from app.modules.example.domain.model import ExampleMessage


class GetExampleMessage:
    def execute(self) -> ExampleMessage:
        return ExampleMessage(text="ok")

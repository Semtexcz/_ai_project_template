from dataclasses import dataclass


@dataclass(frozen=True)
class ExampleMessage:
    text: str

    def normalized(self) -> str:
        return self.text.strip()

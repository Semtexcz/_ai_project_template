from dataclasses import dataclass


@dataclass(frozen=True)
class Todo:
    id: str
    title: str
    completed: bool = False

    def rename(self, title: str) -> "Todo":
        normalized = title.strip()
        if not normalized:
            raise ValueError("Todo title cannot be empty")
        return Todo(id=self.id, title=normalized, completed=self.completed)

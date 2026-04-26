from pathlib import Path
from typing import Any


class CheckpointManager:
    def load(self, checkpoint_path: Path) -> dict[str, Any]:
        pass

    def save(self, checkpoint_path: Path, payload: dict[str, Any]) -> None:
        pass

    def clear(self, checkpoint_path: Path) -> None:
        pass

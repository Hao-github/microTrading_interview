import json
from pathlib import Path

from kline.core.models import TaskConfig
from kline.core.state import IntervalStates


class CheckpointManager:
    def __init__(
        self, config: TaskConfig, file_prefix: str = "checkpoint"
    ) -> None:
        self.checkpoint_dir = config.checkpoint_dir
        self.file_prefix = file_prefix

    def restore_latest(
        self,
    ) -> tuple[int | None, IntervalStates]:
        if (checkpoint_path := self._latest_checkpoint_path()) is None:
            return None, IntervalStates()

        with checkpoint_path.open("r", encoding="utf-8") as checkpoint_file:
            checkpoint_payload = json.load(checkpoint_file)
            return (
                int(checkpoint_payload["offset"]) + 1,
                IntervalStates.from_dict(checkpoint_payload.get("interval_states")),
            )

    def save_snapshot(self, offset: int, interval_states: IntervalStates) -> Path:
        checkpoint_path = self.checkpoint_dir / f"{self.file_prefix}_{offset:020d}.json"
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with checkpoint_path.open("w", encoding="utf-8") as checkpoint_file:
            json.dump(
                {
                    "version": 1,
                    "offset": offset,
                    "interval_states": interval_states.to_dict(),
                },
                checkpoint_file,
                ensure_ascii=True,
                separators=(",", ":"),
            )

        return checkpoint_path

    def clear_latest(self) -> None:
        if (checkpoint_path := self._latest_checkpoint_path()) is not None:
            checkpoint_path.unlink()

    def clear_all(self) -> None:
        if not self.checkpoint_dir.exists():
            return

        for checkpoint_path in self.checkpoint_dir.glob(f"{self.file_prefix}_*.json"):
            checkpoint_path.unlink()

    def _latest_checkpoint_path(self) -> Path | None:
        if not self.checkpoint_dir.exists():
            return None

        checkpoint_paths = sorted(
            self.checkpoint_dir.glob(f"{self.file_prefix}_*.json")
        )
        if not checkpoint_paths:
            return None
        return checkpoint_paths[-1]

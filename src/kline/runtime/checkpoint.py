import pickle
from pathlib import Path

from kline.core.models import TaskConfig
from kline.core.state import IntervalStates


class CheckpointManager:
    PICKLE_PROTOCOL = pickle.HIGHEST_PROTOCOL

    def __init__(self, config: TaskConfig, file_prefix: str = "checkpoint") -> None:
        self.checkpoint_dir = config.checkpoint_dir
        self.file_prefix = file_prefix

    def restore_latest(
        self,
    ) -> tuple[int | None, IntervalStates, int]:
        if (checkpoint_path := self._latest_checkpoint_path()) is None:
            return None, IntervalStates(), 0

        checkpoint_payload = self._load_payload(checkpoint_path)
        interval_states_payload = checkpoint_payload.get("interval_states")
        interval_states = (
            interval_states_payload
            if isinstance(interval_states_payload, IntervalStates)
            else IntervalStates.from_dict(interval_states_payload)
        )
        return (
            int(checkpoint_payload["offset"]) + 1,
            interval_states,
            int(checkpoint_payload["commit_id"]),
        )

    def save_snapshot(
        self, offset: int, interval_states: IntervalStates, commit_id: int
    ) -> Path:
        checkpoint_path = (
            self.checkpoint_dir / f"{self.file_prefix}_{commit_id:020d}.pkl"
        )
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with checkpoint_path.open("wb") as checkpoint_file:
            pickle.dump(
                {
                    "version": 2,
                    "offset": offset,
                    "commit_id": commit_id,
                    "interval_states": interval_states,
                },
                checkpoint_file,
                protocol=self.PICKLE_PROTOCOL,
            )
        return checkpoint_path

    def clear_all(self) -> None:
        if not self.checkpoint_dir.exists():
            return

        for checkpoint_path in self._checkpoint_paths():
            checkpoint_path.unlink()

    def _latest_checkpoint_path(self) -> Path | None:
        if not self.checkpoint_dir.exists():
            return None

        checkpoint_paths = sorted(self._checkpoint_paths())
        if not checkpoint_paths:
            return None
        return checkpoint_paths[-1]

    def _checkpoint_paths(self) -> list[Path]:
        return list(self.checkpoint_dir.glob(f"{self.file_prefix}_*.pkl"))

    @staticmethod
    def _load_payload(checkpoint_path: Path) -> dict:
        with checkpoint_path.open("rb") as checkpoint_file:
            return pickle.load(checkpoint_file)

import os
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
        """Restore the latest checkpoint snapshot if one exists.

        Args:
            None.

        Returns:
            A tuple of ``(start_offset, interval_states, commit_id)``.
        """
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
        """Persist a checkpoint snapshot for the current aggregation progress.

        Args:
            offset: Last processed source offset.
            interval_states: Current in-memory aggregation states.
            commit_id: Commit identifier associated with written output segments.

        Returns:
            Path to the saved checkpoint file.
        """
        checkpoint_path = (
            self.checkpoint_dir / f"{self.file_prefix}_{commit_id:020d}.pkl"
        )
        tmp_checkpoint_path = checkpoint_path.with_suffix(".pkl.tmp")
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 2,
            "offset": offset,
            "commit_id": commit_id,
            "interval_states": interval_states,
        }

        try:
            with tmp_checkpoint_path.open("wb") as checkpoint_file:
                pickle.dump(
                    payload,
                    checkpoint_file,
                    protocol=self.PICKLE_PROTOCOL,
                )
                checkpoint_file.flush()
                os.fsync(checkpoint_file.fileno())

            tmp_checkpoint_path.replace(checkpoint_path)
        finally:
            if tmp_checkpoint_path.exists():
                tmp_checkpoint_path.unlink()

        return checkpoint_path

    def clear_all(self) -> None:
        """Delete all checkpoint files in the checkpoint directory.

        Args:
            None.

        Returns:
            ``None``.
        """
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

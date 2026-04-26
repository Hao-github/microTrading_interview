from pathlib import Path
import re

from kline.core.models import TaskConfig
from kline.io.writer_state import IntervalSegmentState, SegmentStates
from kline.runtime.logger import get_logger


class KlineWriter:
    _COMMIT_PATTERN = re.compile(r"_part_(\d{20})_")

    def __init__(self, config: TaskConfig) -> None:
        self.config = config
        self.logger = get_logger("kline.writer", config.log_dir)
        self.output_dir = Path(self.config.output_dir)
        self.original_file_name = Path(self.config.input_file_path).stem
        self._segment_states = SegmentStates()

    def segment_state_for(self, interval: str) -> IntervalSegmentState:
        output_path = (
            self.output_dir
            / f"kline_{interval}_for_{self.original_file_name}_current.csv.tmp"
        )
        state, created = self._segment_states.get_or_create(interval, output_path)
        if created:
            self.logger.info(
                f"start writing tmp csv file for interval {interval}: {output_path}"
            )
        return state

    def commit_segment(self, commit_id: int, segment_kind: str = "batch") -> list[Path]:
        written_paths: list[Path] = []

        for interval, interval_state in list(self._segment_states.items()):
            committed_path = self.output_dir / (
                f"kline_{interval}_for_{self.original_file_name}"
                f"_part_{commit_id:020d}_{segment_kind}.csv"
            )
            written_paths.append(interval_state.commit_to(committed_path))
            self.logger.info(
                "committed csv file for interval %s: %s, rows=%s",
                interval,
                committed_path,
                interval_state.row_count,
            )

        self._segment_states.clear()
        return written_paths

    def discard_open_segment(self) -> None:
        for interval_state in self._segment_states.values():
            interval_state.discard()
        self._segment_states.clear()

    def has_open_segment(self) -> bool:
        return self._segment_states.has_open_segments()

    def cleanup_outputs_after(self, commit_id: int) -> None:
        for tmp_path in self.output_dir.glob(
            f"kline_*_for_{self.original_file_name}_current.csv.tmp"
        ):
            tmp_path.unlink()

        for output_path in self.output_dir.glob(
            f"kline_*_for_{self.original_file_name}_part_*_*.csv"
        ):
            match = self._COMMIT_PATTERN.search(output_path.name)
            if match and int(match.group(1)) > commit_id:
                output_path.unlink()

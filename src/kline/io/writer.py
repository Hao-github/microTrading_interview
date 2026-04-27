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
        """Get or create the active output segment for an interval.

        Args:
            interval: Interval label such as ``"1m"``.

        Returns:
            The writable ``IntervalSegmentState`` for that interval.
        """
        if interval in self._segment_states:
            return self._segment_states[interval]

        output_path = (
            self.output_dir
            / f"kline_{interval}_for_{self.original_file_name}_current.csv.tmp"
        )
        self.logger.info(
            f"start writing tmp csv file for interval {interval}: {output_path}"
        )
        return self._segment_states.create(interval, output_path)

    def commit_segment(self, commit_id: int, segment_kind: str = "batch") -> list[Path]:
        """Finalize all open segment files and rename them to committed outputs.

        Args:
            commit_id: Monotonic commit identifier used in output filenames.
            segment_kind: Segment suffix such as ``"batch"`` or ``"final"``.

        Returns:
            Paths of the committed output files.
        """
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
        """Discard all currently open temporary segment files.

        Args:
            None.

        Returns:
            ``None``.
        """
        for interval_state in self._segment_states.values():
            interval_state.discard()
        self._segment_states.clear()

    def has_open_segment(self) -> bool:
        """Check whether any interval still has an open temporary segment.

        Args:
            None.

        Returns:
            ``True`` when at least one segment is open; otherwise ``False``.
        """
        return self._segment_states.has_open_segments()

    def cleanup_outputs_after(self, commit_id: int) -> None:
        """Remove temporary files and committed outputs newer than a commit id.

        Args:
            commit_id: Highest committed id that should be kept.

        Returns:
            ``None``.
        """
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

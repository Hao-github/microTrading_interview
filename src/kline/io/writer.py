from pathlib import Path
import re

from kline.core.models import KlineBar, TaskConfig
from kline.io.writer_state import SegmentStates
from kline.runtime.logger import get_logger


class KlineWriter:
    _COMMIT_PATTERN = re.compile(r"_part_(\d{20})_")

    def __init__(self, config: TaskConfig) -> None:
        self.config = config
        self.logger = get_logger("kline.writer", config.log_dir)
        self.output_dir = Path(self.config.output_dir)
        self.segment_dir = self.output_dir / "segments"
        self.segment_dir.mkdir(parents=True, exist_ok=True)
        self.original_file_name = Path(self.config.input_file_path).stem
        self._segment_states = SegmentStates()

    def write_bar(self, interval: str, bar: KlineBar) -> None:
        """Write one bar into the active output segment for an interval.

        Args:
            interval: Interval label such as ``"1m"``.
            bar: K-line bar to append.

        Returns:
            ``None``.
        """
        if interval in self._segment_states:
            self._segment_states[interval].write_bar(bar)
            return

        output_path = self.segment_dir / self._segment_tmp_file_name(interval)
        self.logger.info(
            f"start writing tmp csv file for interval {interval}: {output_path}"
        )
        self._segment_states.create(interval, output_path).write_bar(bar)

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
            committed_path = self.segment_dir / self._segment_output_file_name(
                interval, commit_id, segment_kind
            )
            written_paths.append(interval_state.commit_to(committed_path))
            self.logger.info(
                f"committed csv file for interval {interval}: "
                f"{committed_path}, rows={interval_state.row_count}"
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
        if not self.segment_dir.exists():
            return
        for tmp_path in self.segment_dir.glob(self._segment_tmp_file_name("*")):
            tmp_path.unlink()

        for output_path in self.segment_dir.glob(
            self._segment_output_file_name("*", "*", "*")
        ):
            match = self._COMMIT_PATTERN.search(output_path.name)
            if match and int(match.group(1)) > commit_id:
                output_path.unlink()

    def build_complete_outputs(self) -> None:
        if not self.segment_dir.exists():
            return

        for interval in self.config.intervals:
            segment_paths = sorted(
                self.segment_dir.glob(
                    self._segment_output_file_name(interval, "*", "*")
                )
            )
            if not segment_paths:
                continue

            output_path = self.output_dir / f"{self._base_output_name(interval)}.csv"
            tmp_output_path = (
                self.output_dir / f"{self._base_output_name(interval)}.csv.tmp"
            )

            with tmp_output_path.open("w", encoding="utf-8", newline="") as output_file:
                output_file.write(",".join(KlineBar.csv_fieldnames()) + "\n")

                for segment_path in segment_paths:
                    with segment_path.open(
                        "r", encoding="utf-8", newline=""
                    ) as segment_file:
                        next(segment_file, None)
                        for line in segment_file:
                            output_file.write(line)

            tmp_output_path.replace(output_path)
            self.logger.info(
                f"built merged csv file for interval {interval} "
                f"from {len(segment_paths)} segments"
            )

    def _base_output_name(self, interval: str) -> str:
        return f"kline_{interval}_for_{self.original_file_name}"

    def _segment_tmp_file_name(self, interval: str) -> str:
        return f"{self._base_output_name(interval)}_current.csv.tmp"

    def _segment_output_file_name(
        self, interval: str, commit_id: int | str, segment_kind: str
    ) -> str:
        commit_text = (
            f"{commit_id:020d}" if isinstance(commit_id, int) else str(commit_id)
        )
        return (
            f"{self._base_output_name(interval)}_part_{commit_text}_{segment_kind}.csv"
        )

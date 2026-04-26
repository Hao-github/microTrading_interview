from kline.core import KlineAggregator
from kline.core.models import TaskConfig, TickRecord
from kline.core.state import IntervalStates
from kline.io import CSVReader, KlineWriter
from kline.runtime.checkpoint import CheckpointManager
from kline.runtime.logger import get_logger


class AggregationRunner:
    def __init__(
        self,
        config: TaskConfig,
        reader: CSVReader,
        aggregator: KlineAggregator,
        writer: KlineWriter,
        checkpoint_manager: CheckpointManager,
    ) -> None:
        self.config = config
        self.reader = reader
        self.aggregator = aggregator
        self.writer = writer
        self.checkpoint_manager = checkpoint_manager
        self.logger = get_logger("kline.runner", config.log_dir)

    def run(self) -> None:
        start_offset, initial_states = self.checkpoint_manager.restore_latest()
        self.aggregator.interval_states = initial_states
        last_processed_offset: int | None = None

        with self.reader:
            rows = self.reader.read(
                self.config.input_file_path, start_offset=start_offset
            )
            batch: list[TickRecord] = []

            for row in rows:
                batch.append(row)
                last_processed_offset = row.recv_index
                if self._should_commit_batch(len(batch)):
                    self._commit_batch(batch, last_processed_offset)
                    batch = []

            if batch and last_processed_offset is not None:
                self._commit_batch(batch, last_processed_offset)

        final_batch_end_offset = self._final_batch_end_offset(
            last_processed_offset=last_processed_offset,
            start_offset=start_offset,
            initial_states=initial_states,
        )
        final_rows = list(self.aggregator.aggregate((), self.config.intervals))
        if final_rows and final_batch_end_offset is not None:
            self.writer.write_batch(
                final_rows, final_batch_end_offset, segment_kind="final"
            )

        self.checkpoint_manager.clear_all()
        self.logger.info("aggregation pipeline completed successfully")

    def _should_commit_batch(self, batch_size: int) -> bool:
        interval = self.config.checkpoint_interval
        return interval > 0 and batch_size >= interval

    def _commit_batch(self, batch: list[TickRecord], batch_end_offset: int) -> None:
        batch_rows = list(
            self.aggregator.aggregate(batch, self.config.intervals, finalize=False)
        )
        self.writer.write_batch(batch_rows, batch_end_offset)
        self.checkpoint_manager.save_snapshot(
            offset=batch_end_offset,
            interval_states=self.aggregator.interval_states,
        )
        self.logger.info(
            "committed batch ending at offset %s, input_rows=%s, output_rows=%s",
            batch_end_offset,
            len(batch),
            len(batch_rows),
        )

    @staticmethod
    def _final_batch_end_offset(
        *,
        last_processed_offset: int | None,
        start_offset: int | None,
        initial_states: IntervalStates,
    ) -> int | None:
        if last_processed_offset is not None:
            return last_processed_offset
        if start_offset is not None and start_offset > 0:
            return start_offset - 1
        if initial_states.by_interval:
            return 0
        return None

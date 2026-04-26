from kline.core import KlineAggregator
from kline.core.models import TaskConfig
from kline.io import CSVReader, KlineWriter
from kline.runtime.checkpoint import CheckpointManager
from kline.runtime.logger import get_logger


class AggregationRunner:
    def __init__(
        self,
        config: TaskConfig,
        reader: CSVReader,
        writer: KlineWriter,
        checkpoint_manager: CheckpointManager,
    ) -> None:
        self.config = config
        self.reader = reader
        self.checkpoint_manager = checkpoint_manager
        self.writer = writer
        self.logger = get_logger("kline.runner", config.log_dir)
        self.start_offset, self.initial_states, self.commit_id = (
            self.checkpoint_manager.restore_latest()
        )
        self.aggregator = KlineAggregator(
            config=config, initial_states=self.initial_states
        )

    def run(self) -> None:
        self.writer.cleanup_outputs_after(self.commit_id)
        last_processed_offset: int | None = None
        processed_count = 0

        try:
            with self.reader.read(
                self.config.input_file_path, start_offset=self.start_offset
            ) as rows:

                def rows_with_checkpoints():
                    nonlocal last_processed_offset, processed_count

                    for row in rows:
                        last_processed_offset = row.recv_index
                        processed_count += 1
                        yield row

                        interval = self.config.checkpoint_interval
                        if interval > 0 and processed_count % interval == 0:
                            self.commit_id += 1
                            written_paths = self.writer.commit_segment(self.commit_id)
                            self.checkpoint_manager.save_snapshot(
                                offset=row.recv_index,
                                interval_states=self.aggregator.interval_states,
                                commit_id=self.commit_id,
                            )
                            self.logger.info(
                                "committed checkpoint commit_id=%s, offset=%s, segment_files=%s",
                                self.commit_id,
                                row.recv_index,
                                len(written_paths),
                            )

                for interval, bar in self.aggregator.aggregate(
                    rows_with_checkpoints(), self.config.intervals
                ):
                    self.writer.segment_state_for(interval).write_bar(bar)

            if self.writer.has_open_segment():
                self.commit_id += 1
                self.writer.commit_segment(self.commit_id, segment_kind="final")
            self.checkpoint_manager.clear_all()
        except Exception:
            self.writer.discard_open_segment()
            raise
        self.logger.info("aggregation pipeline completed successfully")

import shutil
import uuid
from pathlib import Path

import pytest

from kline import AggregationRunner, CheckpointManager, ConfigLoader, CSVReader, KlineWriter

from tests.conftest import TEST_CONFIG_PATH


def _make_temp_root() -> Path:
    temp_root = Path(".tmp/runner-tests")
    temp_root.mkdir(parents=True, exist_ok=True)
    root = temp_root / f"runner-{uuid.uuid4().hex}"
    root.mkdir()
    return root


def _make_config(root: Path, checkpoint_interval: int = 10):
    config = ConfigLoader().load(TEST_CONFIG_PATH)
    config.output_dir = root / "out"
    config.log_dir = root / "logs"
    config.checkpoint_dir = root / "ckpt"
    config.checkpoint_interval = checkpoint_interval
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.log_dir.mkdir(parents=True, exist_ok=True)
    config.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return config


def _build_runner(config, checkpoint_manager: CheckpointManager) -> AggregationRunner:
    return AggregationRunner(
        config=config,
        reader=CSVReader(config),
        writer=KlineWriter(config),
        checkpoint_manager=checkpoint_manager,
    )


def _read_output_snapshots(output_dir: Path) -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(output_dir.glob("*.csv"))
    }


class CrashAfterFirstSnapshotCheckpointManager(CheckpointManager):
    def __init__(self, config):
        super().__init__(config)
        self._has_crashed = False

    def save_snapshot(self, offset, interval_states, commit_id):
        checkpoint_path = super().save_snapshot(offset, interval_states, commit_id)
        if not self._has_crashed:
            self._has_crashed = True
            raise RuntimeError("simulated crash after checkpoint save")
        return checkpoint_path


def test_runner_generates_commit_id_named_segments_and_clears_checkpoints() -> None:
    root = _make_temp_root()
    config = _make_config(root)

    try:
        runner = _build_runner(config, CheckpointManager(config))

        runner.run()

        output_names = sorted(path.name for path in config.output_dir.glob("*.csv"))
        segment_names = sorted(
            path.name for path in (config.output_dir / "segments").glob("*.csv")
        )
        checkpoint_names = sorted(
            path.name for path in config.checkpoint_dir.glob("*.pkl")
        )

        assert output_names == [
            "kline_1m_for_sample_ticks_100.csv"
        ]
        assert segment_names[0] == (
            "kline_1m_for_sample_ticks_100_part_00000000000000000001_batch.csv"
        )
        assert segment_names[-1] == (
            "kline_1m_for_sample_ticks_100_part_00000000000000000011_final.csv"
        )
        assert checkpoint_names == []
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_runner_cleanup_removes_future_segments_by_commit_id() -> None:
    root = _make_temp_root()
    config = _make_config(root)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    segment_dir = config.output_dir / "segments"
    segment_dir.mkdir(parents=True, exist_ok=True)

    try:
        kept = (
            segment_dir
            / "kline_1m_for_sample_ticks_100_part_00000000000000000001_batch.csv"
        )
        removed = (
            segment_dir
            / "kline_1m_for_sample_ticks_100_part_00000000000000000002_batch.csv"
        )
        tmp_file = segment_dir / "kline_1m_for_sample_ticks_100_current.csv.tmp"
        header = ",".join(
            [
                "symbol",
                "interval",
                "trading_day",
                "open_price",
                "high_price",
                "low_price",
                "close_price",
                "volume",
                "amount",
                "bucket_start_timestamp",
                "bucket_end_timestamp",
                "first_tick_timestamp",
                "last_tick_timestamp",
            ]
        )
        kept.write_text(
            header + "\n000001.SZ,1m,20221110,10,10,10,10,1,10,1,2,1,1\n",
            encoding="utf-8",
        )
        removed.write_text(
            header + "\n000002.SZ,1m,20221110,20,20,20,20,2,40,3,4,3,3\n",
            encoding="utf-8",
        )
        tmp_file.write_text("tmp", encoding="utf-8")
        final_output = config.output_dir / "kline_1m_for_sample_ticks_100.csv"
        final_output.write_text("stale", encoding="utf-8")

        writer = KlineWriter(config)
        writer.cleanup_outputs_after(commit_id=1)

        assert kept.exists()
        assert not removed.exists()
        assert not tmp_file.exists()
        assert final_output.exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_runner_recovers_from_crash_and_matches_clean_run_outputs() -> None:
    crash_root = _make_temp_root()
    clean_root = _make_temp_root()
    crash_config = _make_config(crash_root)
    clean_config = _make_config(clean_root)

    try:
        crashing_runner = _build_runner(
            crash_config,
            CrashAfterFirstSnapshotCheckpointManager(crash_config),
        )
        with pytest.raises(RuntimeError, match="simulated crash"):
            crashing_runner.run()

        checkpoint_names_after_crash = sorted(
            path.name for path in crash_config.checkpoint_dir.glob("*.pkl")
        )
        assert checkpoint_names_after_crash == [
            "checkpoint_00000000000000000001.pkl"
        ]

        recovered_runner = _build_runner(
            crash_config,
            CheckpointManager(crash_config),
        )
        recovered_runner.run()

        clean_runner = _build_runner(
            clean_config,
            CheckpointManager(clean_config),
        )
        clean_runner.run()

        recovered_outputs = _read_output_snapshots(crash_config.output_dir)
        clean_outputs = _read_output_snapshots(clean_config.output_dir)

        assert recovered_outputs == clean_outputs
        assert not any(crash_config.checkpoint_dir.glob("*.pkl"))
        assert not any(crash_config.output_dir.rglob("*.tmp"))
    finally:
        shutil.rmtree(crash_root, ignore_errors=True)
        shutil.rmtree(clean_root, ignore_errors=True)

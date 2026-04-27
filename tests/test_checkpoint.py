import pickle
import shutil
import uuid
from pathlib import Path

from kline import ConfigLoader
from kline.core import (
    IntervalAggregationState,
    IntervalStates,
    SymbolAggregationState,
    TickRecord,
)
from kline.runtime import CheckpointManager

from tests.conftest import TEST_CONFIG_PATH


def _build_interval_states() -> IntervalStates:
    interval_state = IntervalAggregationState.from_interval("1m")
    symbol_state = SymbolAggregationState(watermark=1_668_043_850_000)
    tick = TickRecord(
        symbol="000001.SZ",
        trading_day="20221110",
        timestamp=1_668_043_840_000,
        price=10.5,
        volume=120,
        turnover=1260,
        recv_index=42,
    )
    symbol_state.upsert_bar(
        row=tick,
        interval="1m",
        timestamp_bucket=(1_668_043_800_000, 1_668_043_860_000),
    )
    interval_state.symbol_states[tick.symbol] = symbol_state
    return IntervalStates(by_interval={"1m": interval_state})


def _make_temp_checkpoint_dir() -> Path:
    temp_root = Path(".tmp/checkpoint-tests")
    temp_root.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = temp_root / f"checkpoint-{uuid.uuid4().hex}"
    checkpoint_dir.mkdir()
    return checkpoint_dir


def _make_manager(checkpoint_dir: Path) -> CheckpointManager:
    config = ConfigLoader().load(TEST_CONFIG_PATH)
    config.checkpoint_dir = checkpoint_dir
    return CheckpointManager(config)


def test_checkpoint_restore_latest_returns_none_when_directory_is_empty() -> None:
    checkpoint_dir = _make_temp_checkpoint_dir()
    manager = _make_manager(checkpoint_dir)

    try:
        start_offset, interval_states, commit_id = manager.restore_latest()

        assert start_offset is None
        assert interval_states.by_interval == {}
        assert commit_id == 0
    finally:
        shutil.rmtree(checkpoint_dir, ignore_errors=True)


def test_checkpoint_save_and_restore_round_trip_state() -> None:
    checkpoint_dir = _make_temp_checkpoint_dir()
    manager = _make_manager(checkpoint_dir)
    interval_states = _build_interval_states()

    try:
        checkpoint_path = manager.save_snapshot(
            offset=42, interval_states=interval_states, commit_id=3
        )
        start_offset, restored_states, commit_id = manager.restore_latest()

        assert checkpoint_path.name == "checkpoint_00000000000000000003.pkl"
        assert checkpoint_path.exists()
        assert start_offset == 43
        assert commit_id == 3

        restored_interval_state = restored_states["1m"]
        restored_symbol_state = restored_interval_state.symbol_states["000001.SZ"]
        restored_bar = restored_symbol_state.active_bars[1_668_043_800_000]

        assert restored_interval_state.interval == "1m"
        assert restored_interval_state.interval_ms == 60_000
        assert restored_symbol_state.watermark == 1_668_043_850_000
        assert restored_symbol_state.flushed_until == -1
        assert restored_bar.open_price == 10.5
        assert restored_bar.close_price == 10.5
        assert restored_bar.volume == 120.0
        assert restored_bar.amount == 1260.0

        with checkpoint_path.open("rb") as checkpoint_file:
            payload = pickle.load(checkpoint_file)
        assert payload["version"] == 2
        assert payload["offset"] == 42
        assert payload["commit_id"] == 3
        assert isinstance(payload["interval_states"], IntervalStates)
    finally:
        shutil.rmtree(checkpoint_dir, ignore_errors=True)


def test_checkpoint_restore_latest_uses_highest_commit_id() -> None:
    checkpoint_dir = _make_temp_checkpoint_dir()
    manager = _make_manager(checkpoint_dir)
    interval_states = _build_interval_states()

    try:
        manager.save_snapshot(offset=10, interval_states=interval_states, commit_id=1)
        manager.save_snapshot(offset=20, interval_states=interval_states, commit_id=5)

        start_offset, _, commit_id = manager.restore_latest()

        assert start_offset == 21
        assert commit_id == 5
    finally:
        shutil.rmtree(checkpoint_dir, ignore_errors=True)


def test_checkpoint_clear_all_removes_all_snapshots() -> None:
    checkpoint_dir = _make_temp_checkpoint_dir()
    manager = _make_manager(checkpoint_dir)
    interval_states = _build_interval_states()

    try:
        older_path = manager.save_snapshot(
            offset=10, interval_states=interval_states, commit_id=1
        )
        latest_path = manager.save_snapshot(
            offset=20, interval_states=interval_states, commit_id=2
        )

        manager.clear_all()

        assert not older_path.exists()
        assert not latest_path.exists()
    finally:
        shutil.rmtree(checkpoint_dir, ignore_errors=True)

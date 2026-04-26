import json
import shutil
import uuid
from pathlib import Path

from kline.core import (
    IntervalAggregationState,
    IntervalStates,
    SymbolAggregationState,
    TickRecord,
)
from kline.runtime import CheckpointManager


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


def test_checkpoint_restore_latest_returns_none_when_directory_is_empty() -> None:
    checkpoint_dir = _make_temp_checkpoint_dir()
    manager = CheckpointManager(checkpoint_dir)

    try:
        start_offset, interval_states = manager.restore_latest()

        assert start_offset is None
        assert interval_states.by_interval == {}
    finally:
        shutil.rmtree(checkpoint_dir, ignore_errors=True)


def test_checkpoint_save_and_restore_round_trip_state() -> None:
    checkpoint_dir = _make_temp_checkpoint_dir()
    manager = CheckpointManager(checkpoint_dir)
    interval_states = _build_interval_states()

    try:
        checkpoint_path = manager.save_snapshot(
            offset=42, interval_states=interval_states
        )
        start_offset, restored_states = manager.restore_latest()

        assert checkpoint_path.name == "checkpoint_00000000000000000042.json"
        assert checkpoint_path.exists()
        assert start_offset == 43
        assert restored_states is not None

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

        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        assert payload["version"] == 1
        assert payload["offset"] == 42
    finally:
        shutil.rmtree(checkpoint_dir, ignore_errors=True)


def test_checkpoint_clear_latest_removes_only_newest_snapshot() -> None:
    checkpoint_dir = _make_temp_checkpoint_dir()
    manager = CheckpointManager(checkpoint_dir)
    interval_states = _build_interval_states()

    try:
        older_path = manager.save_snapshot(offset=10, interval_states=interval_states)
        latest_path = manager.save_snapshot(offset=20, interval_states=interval_states)

        manager.clear_latest()
        start_offset, _ = manager.restore_latest()

        assert older_path.exists()
        assert not latest_path.exists()
        assert start_offset == 11
    finally:
        shutil.rmtree(checkpoint_dir, ignore_errors=True)

from pathlib import Path

import pytest

from kline import ConfigLoader

from tests.conftest import SAMPLE_CSV_PATH, TEST_CONFIG_PATH, make_temp_dir, remove_temp_dir


def test_config_loader_loads_test_config() -> None:
    config = ConfigLoader().load(TEST_CONFIG_PATH)

    assert config.input_file_path == Path("tests/sample_ticks_100.csv")
    assert config.intervals == ["1m"]
    assert config.output_format == "csv"
    assert config.checkpoint_interval == 10


def test_config_loader_accepts_w_checkpoint_suffix() -> None:
    assert ConfigLoader._parse_checkpoint_interval("2w") == 20_000


def test_config_loader_rejects_invalid_interval() -> None:
    temp_dir = make_temp_dir("config-loader-tests")
    try:
        config_path = temp_dir / "invalid.ini"
        config_path.write_text(
            "[paths]\n"
            f"input_file_path = {SAMPLE_CSV_PATH.as_posix()}\n"
            f"output_dir = {(temp_dir / 'out').as_posix()}\n"
            f"log_dir = {(temp_dir / 'logs').as_posix()}\n"
            f"checkpoint_dir = {(temp_dir / 'ckpt').as_posix()}\n"
            "\n[runtime]\n"
            "intervals = 1h\n"
            "output_format = csv\n"
            "checkpoint_interval = 1\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="Invalid interval"):
            ConfigLoader().load(config_path)
    finally:
        remove_temp_dir(temp_dir)

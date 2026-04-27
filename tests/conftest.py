from pathlib import Path
import shutil
import uuid


TESTS_DIR = Path(__file__).resolve().parent
TEST_CONFIG_PATH = TESTS_DIR / "config_for_test.ini"
SAMPLE_CSV_PATH = TESTS_DIR / "sample_ticks_100.csv"


def make_temp_dir(prefix: str) -> Path:
    root = Path(".tmp") / prefix
    root.mkdir(parents=True, exist_ok=True)
    path = root / uuid.uuid4().hex
    path.mkdir()
    return path


def remove_temp_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)

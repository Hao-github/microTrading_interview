from pathlib import Path
from typing import Iterable

from ..core.models import KlineBar


class KlineWriter:
    def write_csv(self, rows: Iterable[KlineBar], output_path: Path) -> None:
        pass

    def write_parquet(self, rows: Iterable[KlineBar], output_path: Path) -> None:
        pass

    def write(self, rows: Iterable[KlineBar], output_path: Path, output_format: str = "csv") -> None:
        pass

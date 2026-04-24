from pathlib import Path
from typing import Iterable

from .models import TickRecord


class CSVReader:
    def read(self, file_path: Path) -> Iterable[TickRecord]:
        pass

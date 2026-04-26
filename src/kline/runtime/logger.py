import logging
from pathlib import Path


def setup_logger(
    log_dir: str | Path | None = "logs", name: str = "kline"
) -> logging.Logger:
    """Create and configure a project logger."""
    log_dir = Path(log_dir) if log_dir is not None else Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{name}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def get_logger(
    name: str = "kline", log_dir: str | Path | None = "logs"
) -> logging.Logger:
    """Return a logger and lazily initialize it when needed."""
    return setup_logger(log_dir=log_dir, name=name)

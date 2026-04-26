import logging
from pathlib import Path


_LOGGER_FILES: dict[str, str] = {}


def setup_logger(log_dir: str | Path = "logs", name: str = "kline") -> logging.Logger:
    """Create or reconfigure a project logger."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = (log_dir / f"{name}.log").resolve()
    log_file_str = str(log_file)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    current_log_file = _LOGGER_FILES.get(name)

    if logger.handlers and current_log_file == log_file_str:
        return logger

    for handler in logger.handlers:
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    _LOGGER_FILES[name] = log_file_str

    return logger


def get_logger(name: str = "kline", log_dir: str | Path = "logs") -> logging.Logger:
    """Return a logger and lazily initialize it when needed."""
    return setup_logger(log_dir=log_dir, name=name)

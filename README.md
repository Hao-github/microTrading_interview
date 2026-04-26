# Kline Project

## Overview

This project converts tick-level CSV market data into streaming K-line outputs for
multiple intervals. The current implementation focuses on a small, testable batch
pipeline:

- read tick records from CSV
- aggregate bars by symbol and interval
- tolerate limited out-of-order events with a watermark window
- stream aggregated bars into per-interval CSV files
- persist checkpoint snapshots for resumable processing

## Structure

- `main.py`: CLI entry point
- `src/kline/`: core package
- `data/input/`: raw input CSV files
- `data/output/`: generated K-line files
- `logs/`: runtime logs
- `checkpoints/`: resume state files
- `tests/`: unit tests

## Configuration

Runtime settings are loaded from `config.ini`.

```ini
[paths]
input_file_path = data/sample_input/md_20221110_head_1000000.csv
output_dir = data/output
log_dir = logs
checkpoint_dir = checkpoints

[runtime]
intervals = 1m,5m,10m,30m
output_format = csv
checkpoint_interval = 1000000
```

`log_dir` is used by the reader, aggregator, and writer loggers, so logs now follow
the configured output directory instead of always writing to the default `logs/`.
`checkpoint_interval = 0` disables checkpoint writes.

## Run

```bash
python main.py
```

The program reads `input_file_path` from `config.ini`, aggregates all configured
intervals, and writes one CSV file per interval into `output_dir`.
If a checkpoint exists, processing resumes from the next unread `recv_index`.
After a successful run, the latest checkpoint file is cleared.

## Development

Install the project in editable mode with test dependencies:

```bash
python -m pip install -e .[dev]
```

Run tests:

```bash
python -m pytest
```

## Status

- Implemented: CSV ingestion, interval aggregation, streaming CSV output, config-based logging, checkpoint save/resume
- Not implemented yet: parquet output

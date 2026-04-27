# Kline Project

[中文](README.zh-CN.md) | [English](README.en.md)

## Overview

This project converts tick-level CSV market data into multi-interval K-line CSV
outputs.

The current implementation focuses on a resumable single-process pipeline with
clear module boundaries:

- `CSVReader` streams tick rows from the source CSV
- `KlineAggregator` maintains per-symbol, per-interval aggregation state
- `KlineWriter` commits output segments through `*.csv.tmp -> *.csv`
- `CheckpointManager` persists resume state
- `AggregationRunner` coordinates reading, checkpointing, aggregation, and recovery

## Features

- Multi-interval aggregation such as `1m`, `5m`, `10m`, `30m`
- Watermark-based out-of-order tolerance and delayed flush
- Checkpoint-based resume
- Commit-id-based output segment naming
- Exactly-once output behavior under crash recovery assumptions
- CI-friendly tests based on `tests/sample_ticks_100.csv`

## Project Structure

- `main.py`: CLI entrypoint
- `src/kline/core/`: domain models and aggregation logic
- `src/kline/io/`: CSV reader and segment writer
- `src/kline/runtime/`: config, checkpoint, runner, logger
- `tests/`: unit and behavior tests
- `docs/`: design notes
- `data/input/`: input data directory
- `data/output/`: generated outputs directory

## Configuration

Runtime settings are loaded from `config.ini`, for example:

```ini
[paths]
input_file_path = data/input/md_20221110.csv
output_dir = data/output
log_dir = logs
checkpoint_dir = checkpoints

[runtime]
intervals = 1m,5m,10m,30m
output_format = csv
checkpoint_interval = 1000000
```

Notes:

- `checkpoint_interval = 0` means no intermediate checkpoint commit
- `output_format` currently supports `csv` only
- `ConfigLoader.validate()` prepares directories and validates config before execution

## How Exactly-Once Output Is Achieved

This project does not implement a distributed transactional protocol. Instead,
it achieves exactly-once output behavior for crash recovery in a single-process
file-based pipeline through checkpointing and committed segment files.

The mechanism is:

1. Each checkpoint stores the latest processed `offset`, current aggregation state,
   and the latest committed `commit_id`
2. Output is first written into `*.csv.tmp` files instead of directly into final files
3. Temporary files are promoted to committed segment files only at checkpoint
   boundaries or during finalization
4. On restart, the runner restores the latest checkpoint, deletes any tmp files and
   committed segments newer than the restored `commit_id`, and resumes from the next offset
5. As a result, already committed output is preserved exactly once, while any
   uncheckpointed work is replayed safely

Under the assumptions of atomic file rename, single-process execution, and a
valid checkpoint file, the final visible outputs are effectively exactly-once.

## How It Works

1. Load config and restore the latest checkpoint
2. Remove output segments whose `commit_id` is newer than the restored checkpoint
3. Stream CSV rows into the aggregator
4. Write emitted bars into open `*.csv.tmp` files
5. At each checkpoint boundary:
   commit tmp files, save checkpoint, and advance `commit_id`
6. After all input is consumed:
   flush remaining bars, commit the final segment, and clear checkpoints

## Output Layout

Committed segment files look like:

```text
kline_1m_for_md_20221110_part_00000000000000000001_batch.csv
kline_1m_for_md_20221110_part_00000000000000000011_final.csv
```

Where:

- `part_<id>` is the commit sequence
- `batch` means an intermediate committed segment
- `final` means the last committed segment

## Usage

Install in editable mode with dev dependencies:

```bash
python -m pip install -e .[dev]
```

Run the pipeline:

```bash
python main.py
```

Run tests:

```bash
python -m pytest
```

## Current Scope

Implemented:

- CSV ingestion
- Multi-interval K-line aggregation
- Resume from checkpoint
- Exactly-once output behavior under crash recovery assumptions
- Commit-id-based segment outputs
- Recovery cleanup

Not implemented yet:

- Parquet output
- Multi-process acceleration

# Kline Project / K 线聚合项目

## Overview / 项目概览

This project converts tick-level CSV market data into K-line CSV outputs for
multiple intervals.

本项目将逐笔/切片级 CSV 行情数据聚合为多个周期的 K 线 CSV 输出。

The current implementation focuses on a resumable single-process pipeline with
clear module boundaries:

当前实现重点是一个支持断点续跑的单进程处理流水线，并保持了清晰的模块边界：

- `CSVReader` reads tick rows from the source CSV
- `KlineAggregator` maintains per-symbol/per-interval aggregation state
- `KlineWriter` writes committed segment files through `*.csv.tmp -> *.csv`
- `CheckpointManager` persists resume state
- `AggregationRunner` coordinates streaming, checkpointing, and recovery

- `CSVReader` 负责从源 CSV 中读取 tick 行
- `KlineAggregator` 负责维护按股票、按周期的聚合状态
- `KlineWriter` 负责通过 `*.csv.tmp -> *.csv` 的方式提交输出分段
- `CheckpointManager` 负责持久化断点状态
- `AggregationRunner` 负责协调流式处理、checkpoint 和恢复逻辑

## Features / 功能特性

- Multi-interval aggregation: `1m`, `5m`, `10m`, `30m`
- Limited out-of-order tolerance with watermark-based flushing
- Checkpoint-based resume
- Commit-id-based output segments
- Idempotent recovery by deleting segments newer than the latest checkpoint

- 支持多周期聚合：`1m`、`5m`、`10m`、`30m`
- 基于 watermark 的乱序容忍与延迟 flush
- 基于 checkpoint 的断点续跑
- 基于 `commit_id` 的输出 segment 命名
- 启动时删除超前于 checkpoint 的 segment，从而实现幂等恢复

## Project Structure / 目录结构

- `main.py`: CLI entrypoint / 命令行入口
- `src/kline/core/`: domain models and aggregation logic / 核心模型与聚合逻辑
- `src/kline/io/`: CSV reader and segment writer / CSV 读写模块
- `src/kline/runtime/`: config, checkpoint, runner, logger / 运行时模块
- `docs/`: design notes / 设计说明
- `tests/`: unit and behavior tests / 单元测试与行为测试
- `data/input/`: input CSV files / 输入数据
- `data/output/`: generated output files / 输出数据

## Configuration / 配置说明

Runtime settings are loaded from `config.ini`.

运行参数通过 `config.ini` 加载。

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

Notes / 说明：

- `checkpoint_interval = 0` means no intermediate checkpoint commit.
- `output_format` currently supports `csv` only.
- `ConfigLoader.validate()` is expected to run before pipeline execution.

- `checkpoint_interval = 0` 表示不进行中途 checkpoint 提交。
- `output_format` 当前仅支持 `csv`。
- 默认约定在执行流水线前，`ConfigLoader.validate()` 已经完成校验与目录创建。

## How It Works / 处理流程

1. Load config and restore the latest checkpoint.
2. Remove output segments whose `commit_id` is newer than the restored checkpoint.
3. Stream rows from CSV into the aggregator.
4. Write emitted bars into open `*.csv.tmp` segment files.
5. On every checkpoint boundary:
   commit tmp files, save checkpoint, and advance `commit_id`.
6. When all input is consumed:
   finalize remaining bars, commit the final segment, and clear checkpoints.

1. 加载配置并恢复最新 checkpoint。
2. 删除所有 `commit_id` 大于 checkpoint 的输出 segment。
3. 将 CSV 行流式送入聚合器。
4. 将聚合器吐出的 K 线写入当前打开的 `*.csv.tmp` 文件。
5. 每到一个 checkpoint 边界时：
   提交 tmp 文件、写入 checkpoint，并推进 `commit_id`。
6. 当输入全部消费完成时：
   flush 剩余 K 线、提交 final segment，并清空 checkpoint。

## Output Layout / 输出文件格式

Committed segment files look like:

输出 segment 文件命名示例如下：

```text
kline_1m_for_md_20221110_head_1000000_part_00000000000000000001_batch.csv
kline_1m_for_md_20221110_head_1000000_part_00000000000000000011_final.csv
```

Where:

其中：

- `part_<id>` is the commit sequence / `part_<id>` 表示提交序号
- `batch` means an intermediate committed segment / `batch` 表示中途提交分段
- `final` means the last committed segment / `final` 表示最终提交分段

## Run / 运行方式

```bash
python main.py
```

The program reads `input_file_path`, writes per-interval CSV segments into
`output_dir`, and clears checkpoints after a successful run.

程序会读取 `input_file_path`，将各周期输出写入 `output_dir`，并在成功结束后清理 checkpoint。

## Development / 开发方式

Install editable mode with test dependencies:

安装可编辑模式与测试依赖：

```bash
python -m pip install -e .[dev]
```

Run tests:

运行测试：

```bash
python -m pytest
```

## Current Scope / 当前范围

Implemented / 已实现：

- CSV ingestion / CSV 输入读取
- Multi-interval K-line aggregation / 多周期 K 线聚合
- Resume from checkpoint / checkpoint 断点续跑
- Commit-id-based segment outputs / 基于 commit_id 的 segment 输出
- Recovery cleanup / 恢复时的超前 segment 清理

Not implemented / 暂未实现：

- Parquet output / Parquet 输出
- Multi-process acceleration / 多进程加速
- External metadata manifest / 独立 manifest 元数据文件

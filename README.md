# Kline Project

[中文](docs/README.zh-CN.md) | [English](docs/README.en.md)

A tick-to-K-line aggregation project with checkpoint-based recovery,
multi-interval CSV outputs, exactly-once output behavior under crash recovery
assumptions, and a CI-friendly sample dataset.

一个基于逐笔行情 CSV 的 K 线聚合项目，支持断点续跑、多周期输出，以及适合 CI
的脱敏测试样例，并在崩溃恢复场景下提供 exactly-once 输出语义。

## Quick Start

```bash
python -m pip install -e .[dev]
python main.py
```

## Highlights

- Multi-interval aggregation such as `1m`, `5m`, `10m`, `30m`
- Watermark-based out-of-order tolerance and delayed flush
- Checkpoint persistence and resumable execution
- Commit-id-based output segment files
- CI-friendly tests based on `tests/sample_ticks_100.csv`

## Documentation

- Chinese: [docs/README.zh-CN.md](docs/README.zh-CN.md)
- English: [docs/README.en.md](docs/README.en.md)
- Design notes: [docs/design.md](docs/design.md)

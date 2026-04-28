# Kline Project

[中文](README.zh-CN.md) | [English](README.en.md)

## 项目简介

本项目将逐笔行情 CSV 数据聚合为多周期 K 线 CSV 输出。

当前实现重点在一个支持断点续跑的单进程流水线，并保持了清晰的模块边界：

- `CSVReader`：从源 CSV 中流式读取 tick 数据
- `KlineAggregator`：维护按股票、按周期的聚合状态
- `KlineWriter`：通过 `*.csv.tmp -> *.csv` 的方式提交输出分段
- `CheckpointManager`：持久化断点状态
- `AggregationRunner`：协调读取、聚合、checkpoint 与恢复流程

## 功能特性

- 支持多周期聚合，如 `1m`、`5m`、`10m`、`30m`
- 基于 watermark 的乱序容忍与延迟 flush
- 基于 checkpoint 的断点续跑
- 基于 `commit_id` 的输出分段命名
- 通过 checkpoint 与恢复清理机制实现 crash recovery 下的 exactly-once 输出语义
- 基于 `tests/sample_ticks_100.csv` 的 CI 友好测试集

## 目录结构

- `main.py`：命令行入口
- `src/kline/core/`：核心模型与聚合逻辑
- `src/kline/io/`：CSV 读取与分段写出
- `src/kline/runtime/`：配置、checkpoint、runner、logger
- `tests/`：单元测试与行为测试
- `docs/`：设计说明
- `data/input/`：输入数据目录
- `data/output/`：完整输出目录
- `data/output/segments/`：按 `commit_id` 提交的分段目录

## 配置说明

运行参数通过 `config.ini` 加载，例如：

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

说明：

- `checkpoint_interval = 0` 表示不进行中途 checkpoint 提交
- `output_format` 当前仅支持 `csv`
- 流水线运行前会通过 `ConfigLoader.validate()` 完成参数校验与目录创建

## Exactly-Once 输出如何实现

本项目没有实现分布式事务式的严格 exactly-once 协议，但在单机场景下，
通过“checkpoint + committed segments + 恢复清理”实现了 crash recovery
下的 exactly-once 输出效果。

核心机制如下：

1. checkpoint 同时保存最近处理完成的 `offset`、当前聚合状态，以及最近一次已提交的 `commit_id`
2. 中途输出不会直接写入最终文件，而是先写入 `*.csv.tmp`
3. 只有在 checkpoint 边界或最终收尾时，tmp 文件才会原子性重命名为正式 segment 文件
4. 如果进程崩溃，重启时先恢复 checkpoint，再删除所有 `commit_id` 晚于 checkpoint 的输出 segment 和残留 tmp 文件
5. 随后从 checkpoint 保存的下一个 `offset` 继续处理

因此，在“文件重命名原子、单进程执行、checkpoint 文件本身未损坏”的前提下，
每个已提交 segment 在最终输出中只会生效一次，不会因为崩溃恢复而重复累计。

## 处理流程

1. 加载配置并恢复最新 checkpoint
2. 删除 `commit_id` 晚于 checkpoint 的输出分段
3. 将 CSV 行流式送入聚合器
4. 将已产出的 K 线写入当前打开的 `*.csv.tmp` 文件
5. 每到 checkpoint 边界时：
   提交 tmp 文件、保存 checkpoint、推进 `commit_id`
6. 所有输入消费完成后：
   flush 剩余 K 线、提交 final segment，并清理 checkpoints

## 输出文件格式

完整输出文件示例：

```text
kline_1m_for_md_20221110.csv
```

分段输出文件示例：

```text
segments/kline_1m_for_md_20221110_part_00000000000000000001_batch.csv
segments/kline_1m_for_md_20221110_part_00000000000000000011_final.csv
```

其中：

- 根目录下的完整输出文件用于直接查看最终结果
- `part_<id>` 表示提交序号
- `batch` 表示中途提交的分段
- `final` 表示最终提交的分段
- `segments/` 下保留 exactly-once 恢复所需的提交痕迹

## 使用方式

安装开发依赖：

```bash
python -m pip install -e .[dev]
```

运行主程序：

```bash
python main.py
```

运行测试：

```bash
python -m pytest
```

## 当前范围

已实现：

- CSV 输入读取
- 多周期 K 线聚合
- checkpoint 断点续跑
- crash recovery 下的 exactly-once 输出语义
- 基于 `commit_id` 的 segment 输出
- 恢复时的超前 segment 清理

暂未实现：

- Parquet 输出
- 多进程加速

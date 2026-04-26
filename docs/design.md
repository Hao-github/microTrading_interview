# Design Notes / 设计说明

## 1. Goal / 目标

The project converts market tick CSV data into multi-interval K-line outputs.
Besides correctness, the implementation also targets:

本项目将市场 tick CSV 数据聚合为多周期 K 线输出。除正确性外，设计还重点考虑：

- clear code structure / 清晰的代码结构
- resumable execution / 可断点续跑
- simple and predictable recovery / 简单且可预测的恢复行为

## 2. Core Modules / 核心模块

### `CSVReader`

Responsibility:

职责：

- validate required CSV columns
- parse rows into `TickRecord`
- support `start_offset` filtering

- 校验必需列
- 将 CSV 行解析为 `TickRecord`
- 支持 `start_offset` 过滤

### `KlineAggregator`

Responsibility:

职责：

- maintain per-symbol aggregation state
- flush bars according to interval and watermark
- support `finalize=True` to flush remaining bars at end of input

- 维护按股票的聚合状态
- 基于周期和 watermark flush 已可输出的 K 线
- 支持在输入结束时通过 `finalize=True` flush 剩余 K 线

### `KlineWriter`

Responsibility:

职责：

- keep currently open per-interval `*.csv.tmp` files
- write emitted bars into tmp segments
- commit tmp segments into final CSV files by `commit_id`
- delete uncommitted temp files or stale future segments during recovery

- 管理当前打开的按周期 `*.csv.tmp` 文件
- 将聚合器产出的 K 线写入 tmp segment
- 按 `commit_id` 将 tmp 提交为正式 CSV
- 在恢复时删除未提交 tmp 或超前 segment

### `CheckpointManager`

Responsibility:

职责：

- persist `offset`
- persist aggregation state
- persist current `commit_id`

- 持久化 `offset`
- 持久化聚合状态
- 持久化当前 `commit_id`

### `AggregationRunner`

Responsibility:

职责：

- orchestrate reader, aggregator, writer, and checkpoint manager
- stream rows through the pipeline
- trigger checkpoint commits at configured boundaries
- finalize and clear checkpoint after successful completion

- 协调 reader、aggregator、writer 与 checkpoint manager
- 将输入行流式送入整个流水线
- 在配置的边界触发 checkpoint 提交
- 成功结束后做 final 提交并清理 checkpoint

## 3. Recovery Model / 恢复模型

This project does not implement a full transactional exactly-once protocol.
Instead, it uses a simpler idempotent recovery model:

本项目没有实现严格事务式的 exactly-once 协议，而是采用更简单的幂等恢复模型：

1. checkpoint stores both `offset` and `commit_id`
2. segment files are named by `commit_id`
3. on startup, files with `commit_id` newer than the restored checkpoint are deleted
4. processing resumes from the restored `offset`

1. checkpoint 同时保存 `offset` 与 `commit_id`
2. segment 文件使用 `commit_id` 命名
3. 启动时删除所有 `commit_id` 超前于 checkpoint 的输出文件
4. 再从恢复出的 `offset` 继续处理

This model is easier to reason about than binding output file names directly to
input offsets.

相比直接把输出文件名绑定到输入 offset，这种模型更容易推理和维护。

## 4. Commit Semantics / 提交语义

Intermediate commit:

中途提交：

- current `*.csv.tmp` files are renamed to committed CSV files
- checkpoint is saved with the latest processed `offset`

- 当前 `*.csv.tmp` 被重命名为正式 CSV
- 使用最新处理到的 `offset` 保存 checkpoint

Final commit:

最终提交：

- remaining bars are flushed by `finalize=True`
- remaining tmp files are committed as `final`
- all checkpoints are cleared

- 通过 `finalize=True` flush 剩余 K 线
- 将剩余 tmp 文件提交为 `final`
- 清空所有 checkpoint

## 5. Why Segment Files / 为什么使用 Segment 文件

Using segment files instead of one ever-growing CSV makes recovery easier:

使用 segment 文件而不是一个不断追加的大 CSV，主要是为了让恢复更简单：

- no truncation is required
- no partial final file repair is needed
- recovery can be implemented by deleting future segments

- 不需要截断已有文件
- 不需要修补部分写入的大文件
- 恢复时只需删除超前 segment

## 6. Trade-offs / 设计取舍

- The current design favors correctness and recoverability over the absolute
  simplest code path.
- `commit_id` may skip numbers if a checkpoint boundary produces no committed
  file, which is acceptable for this pipeline.
- The implementation is intentionally single-process for simplicity.

- 当前设计优先考虑正确性与可恢复性，而不是最短代码路径。
- 如果某个 checkpoint 边界没有生成输出文件，`commit_id` 可能跳号；在本项目中这是可以接受的。
- 当前实现有意保持单进程，以降低复杂度。

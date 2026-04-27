# Design Notes / 设计说明

## 1. Goal / 目标

The project converts market tick CSV data into multi-interval K-line outputs.
Besides correctness, the implementation also targets:

本项目将市场 tick CSV 数据聚合为多周期 K 线输出。除正确性外，设计还重点考虑：

- clear code structure / 清晰的代码结构
- resumable execution / 可断点续跑
- predictable recovery / 可预测的恢复行为
- exactly-once visible outputs after crash recovery / 崩溃恢复后的 exactly-once 可见输出

## 2. Core Modules / 核心模块

### `CSVReader`

Responsibility:

- validate required CSV columns
- parse rows into `TickRecord`
- support `start_offset` filtering

职责：

- 校验必需 CSV 列
- 将 CSV 行解析为 `TickRecord`
- 支持 `start_offset` 过滤

### `KlineAggregator`

Responsibility:

- maintain per-symbol aggregation state
- flush bars according to interval and watermark
- support `finalize=True` to flush remaining bars at end of input

职责：

- 维护按股票的聚合状态
- 基于周期和 watermark flush 可输出的 K 线
- 支持在输入结束时通过 `finalize=True` flush 剩余 K 线

### `KlineWriter`

Responsibility:

- keep currently open per-interval `*.csv.tmp` files
- write emitted bars into tmp segments
- commit tmp segments into final CSV files by `commit_id`
- delete uncommitted temp files or stale future segments during recovery

职责：

- 管理当前打开的按周期 `*.csv.tmp` 文件
- 将聚合器产出的 K 线写入 tmp segment
- 按 `commit_id` 将 tmp 提交为正式 CSV
- 在恢复时删除未提交 tmp 或超前 segment

### `CheckpointManager`

Responsibility:

- persist `offset`
- persist aggregation state
- persist current `commit_id`

职责：

- 持久化 `offset`
- 持久化聚合状态
- 持久化当前 `commit_id`

### `AggregationRunner`

Responsibility:

- orchestrate reader, aggregator, writer, and checkpoint manager
- stream rows through the pipeline
- trigger checkpoint commits at configured boundaries
- finalize and clear checkpoint after successful completion

职责：

- 协调 reader、aggregator、writer 与 checkpoint manager
- 将输入行流式送入整个流水线
- 在配置的边界触发 checkpoint 提交
- 成功结束后做 final 提交并清理 checkpoint

## 3. Exactly-Once Output Model / Exactly-Once 输出模型

This project does not use a distributed transactional protocol. Instead, it
achieves exactly-once output behavior for a single-process file pipeline by
combining checkpoints with committed segment files.

本项目没有使用分布式事务协议，而是通过 checkpoint 与已提交 segment
文件的组合，在单进程文件流水线中实现崩溃恢复下的 exactly-once 输出行为。

The model is:

1. each checkpoint stores `offset`, aggregation state, and `commit_id`
2. output is first written into temporary `*.csv.tmp` files
3. only committed segments are visible as final outputs
4. on startup, any temp files and committed segments newer than the restored
   `commit_id` are deleted
5. processing resumes from the next offset after the checkpoint

模型如下：

1. 每个 checkpoint 保存 `offset`、聚合状态和 `commit_id`
2. 输出先写入临时 `*.csv.tmp` 文件
3. 只有已提交的 segment 才会成为最终可见输出
4. 启动恢复时，删除所有临时文件以及 `commit_id` 晚于 checkpoint 的已提交 segment
5. 之后从 checkpoint 之后的下一个 offset 继续处理

This means:

- committed output is preserved exactly once
- uncommitted work may be replayed
- replay does not duplicate final visible outputs because stale future files are removed first

这意味着：

- 已提交输出会被精确保留一次
- 未提交工作可能被重放
- 由于恢复前会先删除超前输出文件，重放不会导致最终可见输出重复

Under the assumptions of atomic rename, single-process execution, and a valid
checkpoint file, this is effectively exactly-once for output files.

在“文件重命名原子、单进程执行、checkpoint 文件有效”这几个前提下，
这套方案对最终输出文件可以视为 effectively exactly-once。

## 4. Commit Semantics / 提交语义

Intermediate commit:

- current `*.csv.tmp` files are renamed to committed CSV files
- checkpoint is saved with the latest processed `offset`

中途提交：

- 当前 `*.csv.tmp` 被重命名为正式 CSV
- 使用最新处理到的 `offset` 保存 checkpoint

Final commit:

- remaining bars are flushed by `finalize=True`
- remaining tmp files are committed as `final`
- all checkpoints are cleared

最终提交：

- 通过 `finalize=True` flush 剩余 K 线
- 将剩余 tmp 文件提交为 `final`
- 清空所有 checkpoint

## 5. Why Segment Files / 为什么使用 Segment 文件

Using segment files instead of one ever-growing CSV makes recovery easier:

- no truncation is required
- no partial final file repair is needed
- recovery can be implemented by deleting future segments

使用 segment 文件而不是一个不断追加的大 CSV，主要是为了让恢复更简单：

- 不需要截断已有文件
- 不需要修补部分写入的大文件
- 恢复时只需删除超前 segment

## 6. Trade-offs / 设计取舍

- The current design favors correctness and recoverability over the absolute simplest code path
- `commit_id` may skip numbers if a checkpoint boundary produces no committed file, which is acceptable here
- The implementation is intentionally single-process for simplicity

- 当前设计优先考虑正确性与可恢复性，而不是最短代码路径
- 如果某个 checkpoint 边界没有生成输出文件，`commit_id` 可能跳号；在本项目中这是可接受的
- 当前实现有意保持单进程，以降低复杂度

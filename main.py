from kline import (
    AggregationRunner,
    CheckpointManager,
    ConfigLoader,
    CSVReader,
    KlineWriter,
)


def main() -> None:
    """运行K线聚合任务的入口函数。

    输入:
        - 默认从当前工作目录读取配置文件 `config.ini`
        - 配置中指定的源数据文件 `paths.input_file_path` (CSV)

    输出:
        - 聚合结果写入 `paths.output_dir`
        - 断点信息写入 `paths.checkpoint_dir`（可用于断点续跑）

    返回:
        None
    """
    config_loader = ConfigLoader()
    config = config_loader.load()

    runner = AggregationRunner(
        config=config,
        reader=CSVReader(config),
        writer=KlineWriter(config),
        checkpoint_manager=CheckpointManager(config),
    )
    runner.run()


if __name__ == "__main__":
    main()

"""
这是项目的主入口文件。
就像房子的前门，或者导演喊 "Action" 的地方。
它的主要任务是：配置日志、读取命令行参数，然后启动游戏的核心引擎 GameApp。
"""
from __future__ import annotations

import argparse # 用来读指令
import logging # 用来写日志
from typing import Final # 用来声明变量的最终版本

from settings import SETTINGS # 导入settings.py里的全局设置
from src.core.app import GameApp # 导入游戏核心


# 日志的格式：时间 | 级别(INFO/DEBUG) | 模块名 | 消息内容
# Final 表示这是一个常量，程序运行过程中不应该被改变
LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)7s | %(name)s | %(message)s"


def parse_cli_args() -> argparse.Namespace:
    """
    解析命令行参数。
    就像是服务员听取顾客的特殊要求（比如 "少放辣"）。
    在这里，我们只听取一个要求：--debug，如果加上它，程序就会开启调试模式，输出更多信息。
    """
    parser = argparse.ArgumentParser(
        prog="three_kingdoms",
        description="启动三国六边形策略游戏原型",
    )
    # 添加一个开关参数 --debug
    # action="store_true" 的意思是：只要你在命令行里敲了这个词，这个变量就是 True，否则就是 False。
    parser.add_argument(
        "--debug",
        action="store_true",
        help="开启详细的调试日志输出，用于排查问题",
    )
    return parser.parse_args()


def configure_logging(debug: bool) -> None:
    """
    配置日志系统。
    就像是给记录员定规矩：是只记大事（INFO），还是连芝麻绿豆的小事（DEBUG）都记下来。
    """
    # 如果开启了 debug 模式，就记录所有 DEBUG 级别及以上的日志
    # 否则只记录 INFO 级别及以上（比如 "游戏开始" 这种重要的事）
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=log_level, format=LOG_FORMAT)
    
    # pygame 这个库比较啰嗦，我们强制它只在发生严重警告（WARNING）时才说话，平时闭嘴。
    logging.getLogger("pygame").setLevel(logging.WARNING)


def main() -> None:
    """
    主函数：把所有准备工作串起来。
    1. 解析参数
    2. 设置日志
    3. 创建游戏
    4. 运行游戏
    """
    args = parse_cli_args()
    configure_logging(args.debug)

    # 记录一条日志，告诉大家我们要开始加载游戏了
    logging.getLogger(__name__).info("正在启动游戏应用 (debug模式=%s)", args.debug)
    
    # 创建游戏应用实例，就像把导演请到片场
    app = GameApp(settings=SETTINGS, debug=args.debug)
    
    # 让游戏跑起来！这行代码会进入一个死循环，直到游戏关闭才会结束。
    app.run()


# 这是一个 Python 的惯用写法。
# 意思是：只有当你直接运行这个文件（python main.py）时，才会执行 main()。
# 如果别的程序 import 了这个文件，是不会自动运行游戏的。
if __name__ == "__main__":
    main()

"""
这是游戏的配置文件。
这里集中管理了所有不可变的“游戏设定”，比如屏幕每秒刷多少次（FPS），图片存在哪个文件夹里。
把配置都写在这里，以后想修改游戏的基本设置（比如窗口标题）就不用去翻代码了。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# 自动计算项目的根目录路径。
# __file__ 是这个文件本身的路径，parent 是它的父目录。
# 这样不管你把游戏拷到哪里，它都能找到自己的位置。
BASE_DIR = Path(__file__).parent.resolve()
ASSET_ROOT = BASE_DIR / "assets"


@dataclass(frozen=True)
class Settings:
    """
    用 @dataclass(frozen=True) 装饰的类，相当于一张“只读清单”。
    一旦创建，里面的数据就不能被修改（frozen），防止程序运行中途有人手滑改坏配置。
    """

    fps: int  # 游戏每秒的帧数，比如 60 帧
    asset_root: Path  # 资源文件的根目录
    map_definition_file: Path  # 地图定义的 CSV 文件路径
    kingdoms_file: Path  # 国家定义的 JSON 文件路径
    units_file: Path  # 兵种定义的 JSON 文件路径
    fonts_dir: Path  # 字体文件夹
    graphics_dir: Path  # 图片文件夹
    window_title: str = "三足鼎立"  # 游戏窗口的标题
    borderless: bool = True  # 是否开启无边框（全屏）模式
    icon_slot_size_factor: float = 0.6  # 兵种图标相较于格子大小的比例

    # @property 也是一个魔法，它把一个函数伪装成一个变量。
    # 当你调用 settings.map_graphics_dir 时，它会自动计算并返回路径，而不是让你调用函数。
    @property
    def map_graphics_dir(self) -> Path:
        return self.graphics_dir / "map"  # 地图图片的子目录

    @property
    def ui_graphics_dir(self) -> Path:
        return self.graphics_dir / "ui"  # UI 界面图片的子目录

    @property
    def unit_graphics_dir(self) -> Path:
        return self.graphics_dir / "units"  # 兵种图片的子目录


# 创建一个全局唯一的配置实例
# 我们在这里填入具体的值，程序其他地方只要 import 这个 SETTINGS 变量就可以直接使用
SETTINGS = Settings(
    fps=60,
    asset_root=ASSET_ROOT,
    map_definition_file=ASSET_ROOT / "map" / "definitions.csv",
    kingdoms_file=ASSET_ROOT / "data" / "kingdoms.json",
    units_file=ASSET_ROOT / "data" / "units.json",
    fonts_dir=ASSET_ROOT / "fonts",
    graphics_dir=ASSET_ROOT / "graphics",
)

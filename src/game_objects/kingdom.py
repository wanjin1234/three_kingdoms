"""
国家（Kingdom）类的定义和仓库。
这里管理着游戏里的“势力”，比如魏国、蜀国、吴国。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import pygame as pg


@dataclass(frozen=True)
class Kingdom:
    """定义一个国家的基本信息"""
    kingdom_id: str  # 国家ID，如 "WEI"
    name: str        # 显示名称，如 "魏"
    color: pg.Color  # 代表颜色，如 蓝色


class KingdomRepository:
    """
    国家仓库。
    负责从 kingdoms.json 文件加载国家数据，并提供查询功能。
    """

    def __init__(self, json_file: Path) -> None:
        # 读取 JSON 配置文件
        with json_file.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        
        self._kingdoms: Dict[str, Kingdom] = {}
        for entry in payload:
            # 把 JSON 里的颜色字符串（如 "blue"）转换成 Pygame 的 Color 对象
            color = pg.Color(entry["color"])
            kingdom = Kingdom(
                kingdom_id=entry["id"],
                name=entry["name"],
                color=color,
            )
            self._kingdoms[kingdom.kingdom_id] = kingdom

    def get_color(self, kingdom_id: str) -> pg.Color:
        """
        根据国家 ID 获取它的代表色。
        如果是中立地带或者找不到的国家，就返回灰色。
        """
        kingdom = self._kingdoms.get(kingdom_id)
        if kingdom:
            return kingdom.color
        return pg.Color("gray50") # 默认灰色

    def get(self, kingdom_id: str) -> Kingdom | None:
        """获取国家对象"""
        return self._kingdoms.get(kingdom_id)

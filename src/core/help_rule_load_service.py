from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

import pygame as pg

logger = logging.getLogger(__name__)


class HelpRuleLoadService:
    """帮助规则图片异步加载服务。"""

    def load_help_rule_surfaces(
        self, *, graphics_dir: Path
    ) -> tuple[list[pg.Surface], bool]:
        rule_dir = graphics_dir / "rule"
        raw_list = []
        try:
            for i in range(1, 14):
                img_path = rule_dir / f"rule_{i}.png"
                if not img_path.is_file():
                    logger.warning("规则图片不存在: %s", img_path)
                    continue
                surf = pg.image.load(str(img_path))
                raw_list.append(surf)
        except Exception as exc:
            logger.error("加载规则图片失败: %s", exc)
            return [], True
        if not raw_list:
            return [], True
        # convert() 必须在主线程执行，这里暂存原始 Surface。
        # 主线程在 _render_help_overlay 中检测并转换。
        return raw_list, False

    def start_help_rule_load(
        self,
        *,
        has_surfaces: bool,
        is_loading: bool,
        load_target: Callable[[], None],
    ) -> bool:
        if has_surfaces or is_loading:
            return False
        t = threading.Thread(target=load_target, daemon=True)
        t.start()
        return True

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

import fitz  # PyMuPDF
import pygame as pg

logger = logging.getLogger(__name__)

# PDF 渲染分辨率倍数（相对于 72 DPI），3.0 = 216 DPI
_PDF_SCALE = 3.0


class HelpRuleLoadService:
    """帮助规则 PDF 异步加载服务。"""

    def load_help_rule_surfaces(
        self, *, pdf_path: Path
    ) -> tuple[list[pg.Surface], bool]:
        """将 rules.pdf 每页渲染为 pygame Surface 列表。"""
        if not pdf_path.is_file():
            logger.error("规则PDF不存在: %s", pdf_path)
            return [], True
        try:
            doc = fitz.open(str(pdf_path))
            mat = fitz.Matrix(_PDF_SCALE, _PDF_SCALE)
            raw_list: list[pg.Surface] = []
            for page in doc:
                pix = page.get_pixmap(matrix=mat, alpha=False)
                surf = pg.image.frombuffer(
                    pix.samples, (pix.width, pix.height), "RGB"
                ).copy()  # copy 脱离 fitz 内存管理
                raw_list.append(surf)
            doc.close()
        except Exception as exc:
            logger.error("加载规则PDF失败: %s", exc)
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

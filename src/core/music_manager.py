"""
背景音乐管理器。

负责在游戏不同阶段播放对应的背景音乐：
  - 菜单阶段（LOADING / MODE_SELECT / CHOOSING）：循环播放《长安》
  - 游戏阶段（PLAYING）：从《三国杀主题曲》开始，依次循环播放其余三首战场曲
  - 结算阶段（game_over 得分画面）：循环播放《关羽之歌》
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import pygame as pg

logger = logging.getLogger(__name__)

# 自定义事件：当一首曲目播放完毕后由 pygame.mixer.music 发出
MUSIC_END_EVENT: int = pg.USEREVENT + 10


class MusicManager:
    """背景音乐控制器。"""

    # 三种上下文标识
    CTX_MENU = "menu"
    CTX_GAME = "game"
    CTX_SCORE = "score"

    def __init__(self, music_dir: Path) -> None:
        # 初始化 mixer（如果尚未初始化）
        if not pg.mixer.get_init():
            try:
                pg.mixer.init()
            except pg.error as exc:
                logger.warning("无法初始化音频混音器：%s", exc)
                self._available = False
                return

        self._available = True

        # 注册音乐结束事件，以便在事件循环中推进播放列表
        pg.mixer.music.set_endevent(MUSIC_END_EVENT)

        # 各上下文的曲目列表
        self._playlists: dict[str, List[Path]] = {
            self.CTX_MENU: [
                music_dir / "群星 - 长安.mp3",
            ],
            self.CTX_GAME: [
                music_dir / "小田叔 - 三国杀主题曲.mp3",  # 游戏中固定第一首
                music_dir / "群星 - 千里走单骑.mp3",
                music_dir / "群星 - 华容道.mp3",
                music_dir / "群星 - 长坂坡.mp3",
            ],
            self.CTX_SCORE: [
                music_dir / "赵季平 - 关羽之歌.mp3",
            ],
        }

        self._current_ctx: str | None = None
        self._current_idx: int = 0

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def play_menu(self) -> None:
        """切换到菜单音乐（《长安》）。若已在播放则不重新加载。"""
        self._switch_context(self.CTX_MENU)

    def play_game(self) -> None:
        """切换到游戏内音乐，从《三国杀主题曲》开始。"""
        self._switch_context(self.CTX_GAME, reset=True)

    def play_score(self) -> None:
        """切换到得分结算音乐（《关羽之歌》）。"""
        self._switch_context(self.CTX_SCORE)

    def on_track_end(self) -> None:
        """
        在主事件循环检测到 MUSIC_END_EVENT 时调用。
        自动播放当前上下文的下一首曲目（循环）。
        """
        if not self._available or self._current_ctx is None:
            return
        playlist = self._playlists.get(self._current_ctx, [])
        if not playlist:
            return
        self._current_idx = (self._current_idx + 1) % len(playlist)
        self._play_track(playlist[self._current_idx])

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _switch_context(self, ctx: str, reset: bool = False) -> None:
        """切换音乐上下文。若上下文未变且无需重置，则忽略。"""
        if not self._available:
            return
        if self._current_ctx == ctx and not reset:
            return  # 已在播放对应上下文，无需切换
        self._current_ctx = ctx
        self._current_idx = 0
        playlist = self._playlists.get(ctx, [])
        if not playlist:
            return
        self._play_track(playlist[0])

    def _play_track(self, path: Path) -> None:
        """加载并播放指定曲目（不循环，依靠 MUSIC_END_EVENT 推进）。"""
        if not self._available:
            return
        if not path.exists():
            logger.warning("找不到音乐文件：%s", path)
            return
        try:
            pg.mixer.music.load(str(path))
            pg.mixer.music.play()
            logger.debug("正在播放：%s", path.name)
        except pg.error as exc:
            logger.warning("播放音乐失败 [%s]：%s", path.name, exc)

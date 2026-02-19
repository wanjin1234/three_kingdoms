"""
事件卡系统模块。

事件卡（使用 1 政治点数抽取）：
  每次花费 1 政治点数，从本国事件卡牌堆随机抽取一张，立即触发效果。
  公共事件卡（3 张）被并入每个国家的牌堆中共同洗牌，可以被每个国家抽到。

牌堆设计：
  - 每国独立的牌堆 = 本国事件卡 + 3 张公共事件卡（共同洗牌）
  - 当牌堆抽空时自动重新洗牌（将弃牌堆放回并重洗）

效果类型（effect_type）一览：
  pp                  : 对 target_country 的政治点数加减 effect_value
  morale              : 对 target_country 的民心加减 effect_value
  pp_temp             : 抽卡方本回合临时政治点数 +effect_value（回合结束消失）
  flag_xingluo        : 对蜀汉 pp-1，设置"星落秋风"标志（下次隆中定计+1 PP）
  flag_liukang        : 设置"联刘抗曹"标志（本小回合蜀吴不能互攻）
  flag_hefei          : 设置"合肥十万"标志（本大回合吴攻魏骰点-1）
  flag_she_hushu      : 设置"舍身护主"标志（本小回合吴防御+1）
  flag_hu_recruit     : 设置"胡人袭扰"标志（本小回合魏禁止招募）
  flag_wuwei          : 东吴 PP+1，设置"吴魏媾和"标志（本小回合吴不能攻魏）
  flag_all_attack     : 设置"奖率三军"标志（本大回合全军进攻骰点+1）
  flag_laomaikuai     : 设置"老迈昏聩"标志（下次抽到"江东才俊"无效）
  flag_wuzi           : 设置"五子良将"标志（5小回合内魏进攻+1骰，至多+3）
  conditional_lonzhong: 若荆州属于蜀汉，蜀汉获得"隆中定计"攻吴骰+1技能（可叠加）
  conditional_jingzhu : 若荆州属于东吴，东吴获得"荆州之主"攻蜀骰+1技能（可叠加）
  conditional_ruzhong : 若汉中属于曹魏，曹魏本回合 PP+2
  draw_again_safe     : 再抽一张，若负效果则无效（不懈于内）
  evt_skill_yishen    : 蜀汉持有"一身是胆"技能牌
  unit_mp_plus        : 需点击单位 → 单位本大回合 MP+effect_value（忘身于外）
  unit_dice_perm_def_minus: 需点击单位 → 本大回合骰点+1，永久防御-1（愿打愿挨）
  province_def_plus   : 需点击地块 → 该地块所有单位永久防御+effect_value（江东铁壁）
  unit_atk_plus       : 需点击单位 → 永久攻击力+effect_value（挟帝发令）
  unit_dice_bonus     : 需点击单位 → 本大回合骰点+effect_value（厉兵秣马）
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class EventCardDef:
    """事件卡定义（不可变）"""

    id: str  # 唯一 ID
    name: str  # 显示名称
    deck: str  # 所属牌堆: "SHU" | "WU" | "WEI" | "PUBLIC"
    target_country: str  # 效果目标国: "SHU"|"WU"|"WEI"|"ALL"|"DRAWER"
    description: str  # 效果描述文本
    effect_type: str  # 效果类型 key（见模块文档）
    effect_value: int  # 效果数值（正/负）
    needs_target: bool  # 是否需要玩家点击单位或地块
    target_type: str  # "unit" | "province" | ""


class EventCardDeck:
    """
    事件卡牌堆管理。
    所有国家共用同一个牌堆（28 张全部混合洗牌）。
    - SHU/WU/WEI 卡无论谁抽到，效果始终作用于对应国家。
    - PUBLIC 卡谁抽到就对谁生效（target_country=DRAWER）。
    当牌堆耗尽时自动将弃牌堆重新洗入（循环牌库）。
    """

    COUNTRY_DECKS = ("SHU", "WU", "WEI")

    def __init__(self, json_file: "Path | str") -> None:
        # 加载全部卡牌定义
        json_file = Path(json_file)
        with json_file.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)

        self._all_defs: Dict[str, EventCardDef] = {}
        all_cards: List[EventCardDef] = []

        for entry in raw:
            card = EventCardDef(
                id=entry["id"],
                name=entry["name"],
                deck=entry["deck"],
                target_country=entry["target_country"],
                description=entry["description"],
                effect_type=entry["effect_type"],
                effect_value=entry["effect_value"],
                needs_target=entry["needs_target"],
                target_type=entry["target_type"],
            )
            self._all_defs[card.id] = card
            all_cards.append(card)

        # 单一共享牌堆：所有 28 张混合洗牌
        random.shuffle(all_cards)
        self._draw_pile: List[EventCardDef] = all_cards
        self._discard_pile: List[EventCardDef] = []

    # ------------------------------------------------------------------
    def draw(self, country: str = "") -> EventCardDef | None:
        """
        从共享牌堆抽一张卡（country 参数保留以兼容调用方，但不影响抽牌）。
        若牌堆为空则将弃牌堆洗回重新使用。
        """
        if not self._draw_pile:
            if not self._discard_pile:
                return None
            # 重新洗牌
            self._draw_pile.extend(self._discard_pile)
            self._discard_pile.clear()
            random.shuffle(self._draw_pile)

        card = self._draw_pile.pop()
        self._discard_pile.append(card)
        return card

    def get_definition(self, card_id: str) -> EventCardDef | None:
        """通过 ID 获取卡牌定义"""
        return self._all_defs.get(card_id)

    def remaining(self, country: str = "") -> int:
        """返回共享牌堆中剩余的卡牌数（country 参数仅保留兼容性）"""
        return len(self._draw_pile)

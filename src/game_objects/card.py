"""
卡牌系统模块。
定义卡牌数据结构和卡牌管理器。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class CardDefinition:
    """
    卡牌定义。
    """
    id: str                  # 卡牌唯一ID
    name: str                # 卡牌名称
    country: str             # 所属国家 (SHU, WU, WEI)
    description: str         # 卡牌效果描述
    category: str            # 卡牌类别 (offensive, defensive, summon, buff)


@dataclass
class CardState:
    """
    卡牌运行时状态。
    """
    card_id: str
    is_used: bool = False    # 是否已使用
    
    def use_card(self) -> None:
        """标记卡牌为已使用"""
        self.is_used = True
    
    def reset_card(self) -> None:
        """重置卡牌为未使用状态"""
        self.is_used = False


class CardRepository:
    """
    卡牌仓库。
    负责加载和管理卡牌定义。
    """
    
    def __init__(self, json_file: Path) -> None:
        with json_file.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        
        self._definitions: Dict[str, CardDefinition] = {}
        
        for entry in payload:
            card_def = CardDefinition(
                id=entry["id"],
                name=entry["name"],
                country=entry["country"],
                description=entry["description"],
                category=entry["category"],
            )
            self._definitions[card_def.id] = card_def
    
    def get_definition(self, card_id: str) -> CardDefinition | None:
        """获取卡牌定义"""
        return self._definitions.get(card_id)
    
    def get_cards_by_country(self, country: str) -> List[CardDefinition]:
        """获取某个国家的所有卡牌"""
        return [card for card in self._definitions.values() if card.country == country]


class CardManager:
    """
    卡牌管理器。
    负责管理游戏中的卡牌状态。
    """
    
    def __init__(self, repository: CardRepository, country: str) -> None:
        self.repository = repository
        self.country = country
        self.cards: Dict[str, CardState] = {}
        
        # 初始化该国所有卡牌为未使用状态
        for card_def in repository.get_cards_by_country(country):
            self.cards[card_def.id] = CardState(card_id=card_def.id)
    
    def get_available_cards(self) -> List[CardDefinition]:
        """获取可用的卡牌（未使用的卡牌）"""
        available = []
        for card_id, card_state in self.cards.items():
            if not card_state.is_used:
                card_def = self.repository.get_definition(card_id)
                if card_def:
                    available.append(card_def)
        return available
    
    def get_all_cards(self) -> List[CardDefinition]:
        """获取所有卡牌"""
        all_cards = []
        for card_id in self.cards.keys():
            card_def = self.repository.get_definition(card_id)
            if card_def:
                all_cards.append(card_def)
        return all_cards
    
    def use_card(self, card_id: str) -> bool:
        """使用一张卡牌，返回是否成功"""
        if card_id in self.cards:
            self.cards[card_id].use_card()
            return True
        return False
    
    def is_card_used(self, card_id: str) -> bool:
        """检查卡牌是否已被使用"""
        if card_id in self.cards:
            return self.cards[card_id].is_used
        return False
    
    def reset_all_cards(self) -> None:
        """重置所有卡牌为未使用状态（游戏重新开始时）"""
        for card_state in self.cards.values():
            card_state.reset_card()

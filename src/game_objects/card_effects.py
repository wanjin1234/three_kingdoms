"""
卡牌效果处理模块。
负责管理卡牌效果的应用和状态跟踪。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set
from enum import Enum


class CardEffectType(Enum):
    """卡牌效果类型"""
    BUFF = "buff"              # 增益效果
    OFFENSIVE = "offensive"    # 进攻增益
    DEFENSIVE = "defensive"    # 防守效果
    SUMMON = "summon"         # 召唤效果


@dataclass
class ProvinceEffect:
    """
    格子效果状态。
    记录一个格子上应用的卡牌效果。
    """
    province_id: str
    card_id: str
    card_name: str
    
    # 具体效果属性
    mp_bonus: int = 0          # 行动力奖励
    river_immunity: bool = False  # 跨河惩罚免疫
    terrain_immunity: bool = False  # 地形惩罚免疫
    dice_bonus: int = 0        # 骰点奖励
    protected: bool = False    # 是否受保护（无法进攻）
    river_edge_bonus: bool = False  # 河岸进攻奖励
    stacked_bonus: bool = False  # 堆叠进攻奖励
    wounded_attack_bonus: int = 0  # 受伤部队战斗力奖励 (割须弃袍)
    gexu_guard: bool = False  # 割须弃袍：免除防御最高单位一次所受伤害


@dataclass
class CardEffectManager:
    """
    卡牌效果管理器。
    追踪所有活跃的卡牌效果。
    """
    current_effects: Dict[str, ProvinceEffect] = field(default_factory=dict)  # province_id -> effect
    active_offensive_cards: List[str] = field(default_factory=list)  # 已激活的offensive卡牌ID
    
    def add_effect(self, province_id: str, card_id: str, card_name: str, effect: ProvinceEffect) -> None:
        """添加卡牌效果到指定格子"""
        effect.province_id = province_id
        effect.card_id = card_id
        effect.card_name = card_name
        self.current_effects[province_id] = effect
    
    def get_effect(self, province_id: str) -> ProvinceEffect | None:
        """获取格子上的效果"""
        return self.current_effects.get(province_id)
    
    def remove_effect(self, province_id: str) -> None:
        """移除格子上的效果"""
        self.current_effects.pop(province_id, None)
    
    def clear_all_effects(self) -> None:
        """清除所有效果（通常在大回合结束时调用）"""
        self.current_effects.clear()
        self.active_offensive_cards.clear()
    
    def activate_offensive_card(self, card_id: str) -> bool:
        """
        激活offensive类卡牌。这些卡牌在战斗时生效，而不是作为格子效果。
        
        Args:
            card_id: 卡牌ID
            
        Returns:
            是否成功激活
        """
        if card_id not in ["card_zhenjing_huaxia_shu", "card_huoshao_lianying"]:
            return False
        
        if card_id not in self.active_offensive_cards:
            self.active_offensive_cards.append(card_id)
        return True
    
    def is_offensive_card_active(self, card_id: str) -> bool:
        """检查offensive卡牌是否已激活"""
        return card_id in self.active_offensive_cards
    
    def deactivate_offensive_card(self, card_id: str) -> None:
        """停用offensive卡牌效果"""
        if card_id in self.active_offensive_cards:
            self.active_offensive_cards.remove(card_id)
    
    def apply_card_effect(self, card_id: str, card_name: str, province_id: str, country: str) -> bool:
        """
        应用卡牌效果。
        
        Args:
            card_id: 卡牌ID
            card_name: 卡牌名称
            province_id: 目标格子ID
            country: 玩家国家 (SHU, WU, WEI)
            
        Returns:
            是否成功应用
        """
        effect = ProvinceEffect(province_id, card_id, card_name)
        
        # 根据卡牌类型创建对应的效果
        if card_id == "card_baiyue_dujiang":  # 白衣渡江 (吴国)
            effect.river_immunity = True
            effect.dice_bonus = 1
            self.add_effect(province_id, card_id, card_name, effect)
            return True
            
        elif card_id == "card_touduo_yinping":  # 偷渡阴平 (魏国)
            effect.mp_bonus = 2
            effect.terrain_immunity = True
            self.add_effect(province_id, card_id, card_name, effect)
            return True
        
        elif card_id == "card_gexu_qibao":  # 割须弃袍 (魏国)
            effect.gexu_guard = True
            self.add_effect(province_id, card_id, card_name, effect)
            return True
        
        elif card_id == "card_jiangdong_zhiti":  # 江东止啼 (魏国)
            effect.dice_bonus = 2
            self.add_effect(province_id, card_id, card_name, effect)
            return True
            
        elif card_id == "card_kongcheng_mouce":  # 空城妙计 (蜀国)
            effect.protected = True
            self.add_effect(province_id, card_id, card_name, effect)
            return True
            
        # note: `card_zhenjing_huaxia_shu` is an offensive card that should be
        # activated globally via Enter. It does not apply a per-province effect
        # and therefore is NOT handled here.
            
        elif card_id == "card_huoshao_lianying":  # 火烧连营 (吴国) - offensive，针对堆叠部队
            effect.stacked_bonus = True
            self.add_effect(province_id, card_id, card_name, effect)
            return True
        
        elif card_id == "card_qilin_qishu":  # 七擒七纵 (蜀国) - summon
            # summon类卡牌：不设置格子保护，仅用于触发召唤
            self.add_effect(province_id, card_id, card_name, effect)
            return True
        
        elif card_id == "card_guanmu_xiangkan":  # 刮目相看 (吴国) - summon
            # summon类卡牌：不设置格子保护，仅用于触发召唤
            self.add_effect(province_id, card_id, card_name, effect)
            return True
        
        return False
    
    def has_effect(self, province_id: str) -> bool:
        """检查器子是否有效果"""
        return province_id in self.current_effects
    
    def get_affected_provinces(self) -> Set[str]:
        """获取所有有效果的格子ID"""
        return set(self.current_effects.keys())

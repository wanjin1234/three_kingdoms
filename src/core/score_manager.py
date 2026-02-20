"""
分数管理器。
负责计算和存储各国的分数。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# 特殊地点分数配置（仅作参考；实际计分以每个 Province 对象的 victory_point 字段为准）
# 格式：地点名 -> (分数，所属势力)
SPECIAL_LOCATIONS = {
    # 蜀汉
    "Hanzhong": (3, "SHU"),  # 汉中 3 分
    "Jingzhou": (3, "SHU"),  # 荆州 3 分
    "Chengdu": (5, "SHU"),  # 成都 5 分
    # 曹魏
    "Liangzhou": (3, "WEI"),  # 凉州 3 分
    "Youzhou": (2, "WEI"),  # 幽州 2 分
    "Xiangyang": (2, "WEI"),  # 襄阳 2 分
    "Hefei": (2, "WEI"),  # 合肥 2 分
    "Changan": (3, "WEI"),  # 长安 3 分
    "Luoyang": (5, "WEI"),  # 洛阳 5 分
    # 孙吴
    "Wuchang": (2, "WU"),  # 武昌 2 分
    "Changsha": (2, "WU"),  # 长沙 2 分
    "Jianye": (5, "WU"),  # 建业 5 分
}

# 普通地形分数
NORMAL_TERRAIN_SCORE = 0.5


@dataclass
class ScoreRecord:
    """记录某一时刻的分数状态"""

    shu_score: float = 0.0
    wei_score: float = 0.0
    wu_score: float = 0.0

    # 开局分数（用于计算净得分）
    shu_initial: float = 0.0
    wei_initial: float = 0.0
    wu_initial: float = 0.0

    # 民心等级
    shu_people_support: int = 0
    wei_people_support: int = 0
    wu_people_support: int = 0

    # 占领的重要地点列表
    shu_special: List[str] = field(default_factory=list)
    wei_special: List[str] = field(default_factory=list)
    wu_special: List[str] = field(default_factory=list)

    # 普通地块数量
    shu_normal: int = 0
    wei_normal: int = 0
    wu_normal: int = 0


class ScoreManager:
    """
    分数管理器。
    负责计算各国分数、记录开局分数、判断胜利条件。
    """

    def __init__(self) -> None:
        self.initial_scores: Dict[str, float] = {
            "SHU": 0.0,
            "WEI": 0.0,
            "WU": 0.0,
        }
        self.initial_recorded = False

    def calculate_province_score(self, province) -> float:
        """
        计算单个地块的分数。
        直接使用 Province.victory_point（来自 CSV point 列）作为权威分值，
        避免硬编码字典与实际数据失一致的问题。

        Args:
            province: Province 对象

        Returns:
            该地块的分数
        """
        # 直接返回地块自身记录的分值（来自 definitions.csv 的 point 列）
        return float(province.victory_point)

    def calculate_country_score(
        self, provinces: List, country_stats: Dict[str, Dict[str, int]]
    ) -> Dict[str, float]:
        """
        计算各国当前总分。

        Args:
            provinces: 所有地块列表
            country_stats: 国家属性字典（包含民心等级）

        Returns:
            {国家代码：总分} 字典
        """
        scores = {"SHU": 0.0, "WEI": 0.0, "WU": 0.0}

        for prov in provinces:
            if not prov.country or prov.country not in scores:
                continue

            score = self.calculate_province_score(prov)
            scores[prov.country] += score

        return scores

    def record_initial_scores(self, provinces: List) -> None:
        """
        记录开局分数。
        应该在游戏开始时调用一次。

        Args:
            provinces: 所有地块列表
        """
        current = self.calculate_country_score(provinces, {})
        self.initial_scores = current
        self.initial_recorded = True

    def get_net_scores(
        self, provinces: List, country_stats: Dict[str, Dict[str, int]] | None = None
    ) -> Dict[str, float]:
        """
        计算净得分（当前分数 - 开局分数）。

        Args:
            provinces: 所有地块列表
            country_stats: 国家属性字典（可选）

        Returns:
            {国家代码：净得分} 字典
        """
        if not self.initial_recorded:
            self.record_initial_scores(provinces)

        current = self.calculate_country_score(provinces, country_stats or {})

        net = {}
        for country in ["SHU", "WEI", "WU"]:
            net[country] = current.get(country, 0.0) - self.initial_scores.get(
                country, 0.0
            )

        return net

    def get_detailed_scores(
        self, provinces: List, country_stats: Dict[str, Dict[str, int]]
    ) -> ScoreRecord:
        """
        获取详细分数信息。

        Args:
            provinces: 所有地块列表
            country_stats: 国家属性字典

        Returns:
            ScoreRecord 对象
        """
        record = ScoreRecord()

        # 计算当前分数和占领情况
        for prov in provinces:
            if not prov.country or prov.country not in ["SHU", "WEI", "WU"]:
                continue

            score = self.calculate_province_score(prov)

            # 累加总分
            if prov.country == "SHU":
                record.shu_score += score
            elif prov.country == "WEI":
                record.wei_score += score
            elif prov.country == "WU":
                record.wu_score += score

            # 记录特殊地点（victory_point > 普通地块分值即为特殊城市）
            if prov.victory_point > NORMAL_TERRAIN_SCORE:
                if prov.country == "SHU":
                    record.shu_special.append(prov.name)
                elif prov.country == "WEI":
                    record.wei_special.append(prov.name)
                elif prov.country == "WU":
                    record.wu_special.append(prov.name)
            else:
                # 普通地块
                if prov.country == "SHU":
                    record.shu_normal += 1
                elif prov.country == "WEI":
                    record.wei_normal += 1
                elif prov.country == "WU":
                    record.wu_normal += 1

        # 民心等级
        if country_stats:
            for country in ["SHU", "WEI", "WU"]:
                stats = country_stats.get(country, {})
                support = stats.get("people_support", 0)
                if country == "SHU":
                    record.shu_people_support = support
                elif country == "WEI":
                    record.wei_people_support = support
                elif country == "WU":
                    record.wu_people_support = support

        # 如果没有记录过开局分数，现在记录
        if not self.initial_recorded:
            self.record_initial_scores(provinces)

        record.shu_initial = self.initial_scores.get("SHU", 0.0)
        record.wei_initial = self.initial_scores.get("WEI", 0.0)
        record.wu_initial = self.initial_scores.get("WU", 0.0)

        return record

    def check_tianxia_guixin(
        self, provinces: List, country_stats: Dict[str, Dict[str, int]]
    ) -> str | None:
        """
        检查是否有势力达成"天下归心"胜利条件。
        条件：民心等级达 5 级，且同时占领洛阳、成都、建邺。

        Args:
            provinces: 所有地块列表
            country_stats: 国家属性字典

        Returns:
            获胜国家代码，如果没有达成则返回 None
        """
        # 检查各国是否满足条件
        for country in ["SHU", "WEI", "WU"]:
            stats = country_stats.get(country, {})
            support = stats.get("people_support", 0)

            if support < 5:
                continue

            # 检查是否占领三个关键城市
            owns_luoyang = False
            owns_chengdu = False
            owns_jianye = False

            for prov in provinces:
                if prov.country != country:
                    continue
                if prov.name == "Luoyang":
                    owns_luoyang = True
                elif prov.name == "Chengdu":
                    owns_chengdu = True
                elif prov.name == "Jianye":
                    owns_jianye = True

            if owns_luoyang and owns_chengdu and owns_jianye:
                return country

        return None

    def get_winner_by_score(
        self, provinces: List, country_stats: Dict[str, Dict[str, int]]
    ) -> Tuple[str, Dict[str, float]]:
        """
        根据"一代枭雄"规则判定获胜者。
        净占领地块计分排名第一的获胜。

        Args:
            provinces: 所有地块列表
            country_stats: 国家属性字典

        Returns:
            (获胜国家代码，净得分字典)
        """
        net_scores = self.get_net_scores(provinces, country_stats)

        # 找出最高分
        max_score = max(net_scores.values())
        winners = [c for c, s in net_scores.items() if s == max_score]

        if len(winners) == 1:
            return winners[0], net_scores
        else:
            # 平局情况，返回空字符串表示无单一获胜者
            return "", net_scores

class lattice:
    """管理棋盘格子状态"""

    def __init__(self, country, unit, terrain, defend, position, vic_point):
        self.country = country  # 所属国家
        self.unit = unit  # 上面站着哪些单位，是一个列表list，例如：["infantry","infantry","cavalry"]
        self.terrain = terrain  # 地形类型
        self.defend = defend  # 单位总防御
        self.pos = position  # 六个顶点的位置
        self.point = vic_point  # 胜利点计分

        # 所有格子的信息,编号按列从左到右、从上到下

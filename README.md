# 三足鼎立 —— 三国六边形策略游戏

> 一款基于 **Python + Pygame** 的回合制六边形棋盘策略游戏，以三国时期为背景，玩家可选择魏、蜀、吴三国之一，与 AI 对手在中原大地上展开争霸。
> （本文档部分内容由AI生成）

---

## 目录

1. [游戏简介](#一游戏简介)
2. [快速开始](#二快速开始运行游戏)
3. [项目文件结构](#三项目文件结构)
4. [整体架构思路](#四整体架构思路)
5. [核心模块详解](#五核心模块详解)
6. [游戏机制实现](#六游戏机制实现)
7. [数据配置说明](#七数据配置说明)

---

<a id="一游戏简介"></a>

## 一、游戏简介

本游戏是一款**回合制六边形棋盘（Hex Grid）策略游戏**：

- **三方势力**：曹魏（WEI）、蜀汉（SHU）、孙吴（WU）
- **地图**：由若干六边形格子（Province，省份/地块）拼成的中国地图
- **胜负**：通过占领重要城池（洛阳、成都、建业……）积累胜利点数，大回合结束时结算
- **核心玩法**：移动部队 → 发动战斗 → 使用策略卡牌 → 抽取随机事件卡

---

<a id="二快速开始运行游戏"></a>

## 二、快速开始（运行游戏）

### 方式一：直接下载 EXE（推荐，无需安装 Python）

前往本项目的 **[GitHub Releases 页面](../../releases)**，下载最新版本的 `三足鼎立.exe`，双击即可运行，无需额外安装步骤。

> **注意**：首次运行时 Windows 可能弹出安全提示，点击"仍要运行"即可。EXE 已将所有资源打包在内，不依赖外部文件。

### 方式二：从源码运行（适合想学习代码的同学）

#### 环境要求

- Python 3.10 或更高版本
- 推荐在虚拟环境（venv / conda）中运行

#### 安装步骤

```bash
# 1. 进入项目根目录
cd three_kingdoms

# 2. 安装依赖（主要是 pygame）
pip install -r requirements.txt

# 3. 运行游戏
python main.py

# 可选：开启调试日志（会在终端输出大量内部信息，方便排查问题）
python main.py --debug
```

#### 依赖一览（requirements.txt）

| 库       | 用途                     |
| -------- | ------------------------ |
| `pygame` | 图形渲染、事件处理、音频 |

> **规则书**：游戏内规则书以 PNG 图片形式存放于 `assets/graphics/rule/rule_1.png` 等文件，由 Pygame 直接加载，无需任何额外依赖。

---

<a id="三项目文件结构"></a>

## 三、项目文件结构

```text
three_kingdoms/
├── main.py                    ← 程序唯一入口（启动游戏）
├── settings.py                ← 全局配置（分辨率、帧率、资源路径）
├── requirements.txt           ← Python 依赖列表
│
├── assets/                    ← 所有静态资源
│   ├── data/                  ← JSON 数据配置
│   │   ├── kingdoms.json      ← 三个国家的基础数据（名称、颜色）
│   │   ├── units.json         ← 所有兵种数值（移动力、攻防、射程）
│   │   ├── cards.json         ← 策略卡牌定义
│   │   └── event_cards.json   ← 事件卡牌定义（含效果类型）
│   ├── map/
│   │   └── definitions.csv    ← 地图格子定义（坐标、地形、归属、分值）
│   ├── graphics/              ← 所有图片
│   │   ├── map/               ← 地形贴图（平原、山地、河流……）
│   │   ├── units/             ← 各兵种图标
│   │   └── ui/                ← 界面按钮、面板背景等
│   └── fonts/                 ← 字体文件
│
├── src/                       ← 全部源代码
│   ├── core/                  ← 游戏核心逻辑
│   │   ├── app.py             ← GameApp：游戏总编排器（状态机 + 主循环）
│   │   ├── app_contexts.py    ← 各服务的"调用契约"（数据传递结构体）
│   │   ├── app_context_factory.py  ← 统一构建契约对象的工厂
│   │   ├── state_models.py    ← 回合状态的数据模型（TurnState）
│   │   ├── combat.py          ← 战斗结算表（CRT）和骰点逻辑
│   │   ├── ai_service.py      ← AI 决策逻辑
│   │   ├── movement_service.py ← 部队移动与路径计算
│   │   ├── card_play_service.py ← 策略卡牌打出逻辑
│   │   ├── event_card_service.py ← 事件卡抽取与结算
│   │   ├── turn_orchestration_service.py  ← 回合推进编排
│   │   ├── score_manager.py   ← 分数计算与记录
│   │   ├── camera.py          ← 地图摄像机（拖拽与缩放）
│   │   └── ...（其余领域服务）
│   │
│   ├── game_objects/          ← 游戏领域对象（纯数据）
│   │   ├── kingdom.py         ← 国家（Kingdom）数据类
│   │   ├── unit.py            ← 兵种定义（UnitDefinition）和单位状态（UnitState）
│   │   ├── card.py            ← 策略卡牌定义与运行时状态
│   │   └── event_card.py      ← 事件卡定义与牌堆管理
│   │
│   ├── map/                   ← 地图子系统
│   │   ├── province.py        ← Province（六边形格子）数据类
│   │   ├── map_manager.py     ← 地图管理器（加载/绘制/寻路）
│   │   └── geometry.py        ← 六边形几何计算工具
│   │
│   ├── ui/                    ← UI 组件
│   │   ├── info_panel.py      ← 右侧信息面板
│   │   └── panels.py          ← 其他面板组件
│   │
│   └── music/                 ← 音乐播放管理
│
└── tests/                     ← 自动化测试（最小回归测试）
```

---

<a id="四整体架构思路"></a>

## 四、整体架构思路

> 理解这一节，你就能看懂整个项目的"设计哲学"。

### 4.1 Pygame 的游戏主循环

所有 Pygame 游戏的骨架都是一个**无限循环（Game Loop）**，每秒执行 60 次（60 FPS），本项目也不例外。

实际运行代码在 `src/core/runtime_loop_service.py` 的 `run()` 方法里（由 `GameApp.run()` 委托调用）：

```python
# src/core/runtime_loop_service.py  （简化版）
def run(self, app) -> None:
    app._running = True
    while app._running:               # ← 死循环，直到玩家关闭窗口
        app.event_manager.process()   # ① 处理事件（鼠标、键盘、窗口变化……）
        app._update()                 # ② 更新逻辑（AI行动、动画计时、状态切换……）
        if app._dirty:                # ③ 只有"画面需要更新"时才重新绘制
            app._render()             #    清屏 → 画地图 → 画单位 → 画UI面板
            app._present_frame()      #    把画好的内容显示到屏幕
            app._dirty = False
        else:
            pg.time.wait(4)           #    画面无变化时让出CPU，省电
        app.clock.tick(app.settings.fps)  # 控制帧率上限为 60 FPS
```

**`_dirty` 脏标记优化**：只有游戏内容真正发生变化（玩家操作、动画播放等）时才触发重绘，静止画面不做无意义的渲染，可以显著降低 CPU/GPU 占用。

**三步流程总结**：

```text
每一帧:
  ① event_manager.process()  ← 把操作系统消息（点击、按键）翻译成游戏能理解的事件
  ② _update()                ← 根据当前状态执行对应逻辑（AI? 动画? 等待玩家?）
  ③ _render()                ← 把最新的游戏数据画到屏幕上
```

### 4.2 状态机：游戏"在哪个界面"

游戏任意时刻只能处于**一种状态（State）**，状态决定了"现在该响应哪些操作、该画什么内容"。  
如果没有状态机，`_update()` 和 `_render()` 里就需要写无数个 `if 现在是主菜单... elif 现在在游戏中...`，极难维护。

本项目在 `src/core/app.py` 里用 Python 的 `Enum`（枚举）定义了 `GameState`：

```python
# src/core/app.py
class GameState(Enum):
    LOADING     = auto()   # 启动加载界面（初始化资源、显示 Logo）
    MODE_SELECT = auto()   # 模式选择界面（单人 / 双人？）
    CHOOSING    = auto()   # 势力选择界面（选魏 / 蜀 / 吴）
    PLAYING     = auto()   # 正式游戏中（地图操作、战斗、卡牌……）
```

**状态切换示意**：

```text
启动
  ↓
LOADING（加载资源）
  ↓  资源加载完成
MODE_SELECT（选择单人/多人）
  ↓  点击"单人"
CHOOSING（点击魏/蜀/吴旗帜）
  ↓  点击某个势力
PLAYING（游戏主界面，循环直到结束）
```

切换方式非常简单，就是直接修改 `self.state`：

```python
# 比如玩家点击了"开始游戏"按钮
self.state = GameState.MODE_SELECT   # 状态机立刻切换
# 下一帧，_update() 和 _render() 就会执行 MODE_SELECT 对应的逻辑
```

`_render()` 内部根据当前状态调用不同的渲染函数：

```python
def _render(self) -> None:
    if self.state == GameState.LOADING:
        self._render_loading()         # 画加载界面
    elif self.state == GameState.MODE_SELECT:
        self._render_mode_select()     # 画模式选择界面
    elif self.state == GameState.CHOOSING:
        self._render_choosing()        # 画势力选择界面
    elif self.state == GameState.PLAYING:
        self._render_playing()         # 画游戏主界面（调用 GameplayRenderService）
```

### 4.3 服务化架构：为什么代码被拆成那么多文件？

如果把所有游戏逻辑都塞进 `app.py` 一个文件，它会膨胀到上万行——谁也看不懂，谁也不敢改。  
因此，本项目把各个"业务功能"拆分为独立的**服务类（Service）**，每个服务类只专注一件事。

`GameApp` 在 `__init__` 里把所有服务实例化并保存为自己的属性：

```python
# src/core/app.py（__init__ 中，简化）
self.movement_service            = MovementService()
self.combat_flow_service         = CombatFlowService()
self.combat_resolution_service   = CombatResolutionService()
self.ai_service                  = AIService()
self.card_play_service           = CardPlayService()
self.event_card_service          = EventCardService()
self.turn_orchestration_service  = TurnOrchestrationService()
self.score_manager               = ScoreManager()
self.gameplay_render_service     = GameplayRenderService()
self.runtime_loop_service        = RuntimeLoopService()
# ... 还有十几个
```

需要某个功能时，`GameApp` 直接委托给对应的 Service：

```python
# 玩家点击格子，触发移动
self.movement_service.handle_movement(self, target_province)

# AI 轮到曹魏行动
self.ai_service.run_turn_with_context(context)

# 回合结束，切换到下一个国家
self.turn_orchestration_service.advance_country_turn_with_context(context)
```

**比喻**：`GameApp` 是总导演，各个 Service 是专业演员——导演只说"你上台演战斗场景"，具体怎么演（骰子怎么算、血量怎么扣）是演员自己的事，导演不需要知道细节。

**这样做的好处**：

- 想修改战斗规则？只需改 `combat_flow_service.py`，不会影响 AI 或 UI
- 想给战斗写自动化测试？直接测试 `CombatFlowService`，不需要启动整个游戏
- 多人协作时，每个人负责不同的 Service 文件，几乎不会互相覆盖代码

### 4.4 契约模式（Context / Contract）：服务之间怎么传数据

**问题**：Service 函数需要数据（比如"目标格子"、"攻击方部队列表"），从哪里拿？

**方案一（不好）**：把整个 `GameApp` 传进去

```python
# ❌ 危险写法：函数可以访问 app 的任意属性，随意修改游戏状态
def run_ai_turn(self, app: GameApp) -> None:
    # 里面可以改 app.state、app.player_country……任何东西都能改
    # 两个文件深度耦合，改 app.py 可能导致 ai_service.py 莫名出错
```

**方案二（本项目采用）**：只传一个精简的"数据包"（Context）

```python
# ✅ 安全写法：函数只能拿到 Context 里明确列出的字段

# 第一步：在 src/core/app_contexts.py 里定义这次调用需要哪些数据
@dataclass
class AIRunTurnContext:
    map_manager: MapManager   # 地图数据
    player_country: str       # 当前行动的 AI 国家
    hex_side: float           # 格子边长（用于距离计算）
    pp: int                   # 当前政治点数
    on_recruit: Callable      # 招募单位的回调函数
    on_attack: Callable       # 发起攻击的回调函数
    # 只列出 AI 真正需要的字段，其余 app 内部数据一律不暴露

# 第二步：在 src/core/app_context_factory.py 里统一构建这个数据包
ctx = app_context_factory.build_ai_run_turn_context(app)

# 第三步：GameApp 调用服务时传入数据包
self.ai_service.run_turn_with_context(ctx)

# 第四步：ai_service.py 只能访问 ctx 里定义好的字段，不会越权
def run_turn_with_context(self, context: AIRunTurnContext) -> None:
    provinces = context.map_manager.provinces   # ✅ 允许
    country   = context.player_country          # ✅ 允许
    # self.app.state = ...                      # ❌ 根本拿不到 app
```

> **规律**：凡是函数名带 `_with_context` 后缀的，都表示它使用了这套契约模式。  
> 所有 Context 结构体定义在 `src/core/app_contexts.py`，构建逻辑统一在 `src/core/app_context_factory.py`。

---

<a id="五核心模块详解"></a>

## 五、核心模块详解

### 5.1 地图系统：六边形格子如何工作

#### 六边形坐标

地图由六边形格子拼成。每个格子（`Province`）在逻辑坐标系里有一个 `(x_factor, y_factor)` 坐标，转换为屏幕像素坐标的公式是：

$$
\text{pixel\_x} = x\_factor \times \text{hex\_side}\\
\text{pixel\_y} = y\_factor \times \sqrt{3} \times \text{hex\_side}
$$

其中 `hex_side` 是六边形的边长（像素），会随窗口缩放而变化。

这段逻辑在 `src/map/province.py` 的 `compute_center()` 方法中实现。

#### 相邻关系与寻路

`MapManager` 在初始化时会根据格子坐标自动计算**邻接表**（`_adjacency`），记录每个格子的 6 个相邻格子。  
寻路使用**Dijkstra 算法**（最短路径），考虑地形的移动力消耗（山地更费），结果会缓存起来避免重复计算。

#### Province 的数据结构

```python
@dataclass
class Province:
    province_id: int    # 格子唯一编号
    name: str           # 地名（如"洛阳"）
    country: str        # 当前归属（"WEI" / "SHU" / "WU" / 空字符串）
    terrain: str        # 地形（"plain" 平原 / "mountain" 山地 / "river" 河流）
    defense: float      # 防御加成
    victory_point: float # 占领此格的胜利点数
    units: List[UnitState]  # 当前驻守的部队列表（最多 3 支）
```

### 5.2 单位系统：兵种与状态

#### 不变的"定义" vs 可变的"状态"

本项目把单位拆成两个类，这是游戏开发中的常见模式：

| 类名             | 存储位置                         | 作用                                                       |
| ---------------- | -------------------------------- | ---------------------------------------------------------- |
| `UnitDefinition` | `UnitRepository`（全局只有一份） | 兵种的**固定属性**：移动力、攻击、防御、射程               |
| `UnitState`      | `Province.units` 列表中          | 某个具体单位的**实时状态**：当前血量、剩余行动力、是否混乱 |

**比喻**：`UnitDefinition` 是"骑兵"这个职业的说明书，`UnitState` 是你军队里那个具体的骑兵小张今天的状态。

#### UnitState 的关键字段

```python
@dataclass
class UnitState:
    unit_type: str         # 兵种代号，如 "cavalry"（骑兵）
    hp: int = 2            # 血量（满血=2，受伤=1，死亡则从格子中移除）
    mp: int = 0            # 本回合剩余行动力（从 UnitDefinition.move 每回合刷新）
    is_confused: bool      # 是否处于混乱状态（无法正常行动）
    temp_dice_bonus: int   # 本大回合战斗骰点加成（卡牌效果临时赋予）
    attack_bonus: int      # 永久攻击力加成（某些事件卡永久改变）
    defense_bonus: int     # 永久防御力加成
```

### 5.3 战斗系统：骰子与结算表

战斗采用经典的**CRT（Combat Resolution Table，战斗结算表）**机制：

#### 第一步：计算攻防比

```text
攻击力 = 攻击方所有单位的 attack 之和 + 各种加成
防守力 = 防守方所有单位的 defense 之和 × 地形防御系数
攻防比 = 攻击力 / 防守力  （如 2:1、3:1 等）
```

#### 第二步：投骰子（1～6）

系统随机产生一个 1～6 的骰点，再结合攻防比，在**结算表**里查找结果：

| 骰点 \ 比例 | 1:2     | 1:1      | 2:1     | 3:1     | 4:1     | 5:1        |
| ----------- | ------- | -------- | ------- | ------- | ------- | ---------- |
| 1           | 攻方损2 | 攻方损1  | 攻方损1 | 平      | 平      | 守方退     |
| 2           | 攻方损1 | 攻守均退 | …       | …       | …       | …          |
| …           | …       | …        | …       | …       | …       | …          |
| 6           | 守方退  | 守方退   | 守方损1 | 守方损1 | 守方损1 | 守方损1+退 |

结果缩写含义：

- `A1/A2`：攻方损失 1/2 血
- `D1/DR`：守方损失 1 血 / 强制后退
- `AG/DG`：攻方/守方**撤退**（混乱）
- `C`：双方相持，本回合无伤亡

此逻辑在 `src/core/combat.py` 的 `COMBAT_TABLE` 和 `resolve_combat()` 中实现。

### 5.4 回合系统：大回合与小回合

游戏采用**两层回合制**：

```text
大回合（Major Round）：游戏的一个完整阶段
  └── 小回合（Minor Round）：三个国家各行动一次
        ├── 魏国行动（玩家或 AI）
        ├── 蜀汉行动（玩家或 AI）
        └── 孙吴行动（玩家或 AI）
```

- **小回合开始**：刷新该国所有单位的行动力（`mp`），发放政治点数（PP）
- **小回合结束**：检查是否达成天下统一（胜利条件），切换到下一个国家
- **大回合结束**：结算各国分数，部分临时效果（如某些卡牌加成）清零

回合推进逻辑分布在：

- `src/core/turn_orchestration_service.py`（回合切换编排）
- `src/core/turn_start_orchestration_service.py`（回合开始时的初始化）
- `src/core/major_round_status_service.py`（大回合状态管理）

### 5.5 卡牌系统：策略卡与事件卡

游戏有两套独立的卡牌：

#### 策略卡（Card）

- 每国有自己专属的策略卡组（从 `assets/data/cards.json` 加载）
- 玩家在自己回合内手动打出，效果立即生效（如召唤单位、强化攻防）
- 分为 `offensive`（进攻）/ `defensive`（防御）/ `summon`（征兵）/ `buff`（增益）等类别

#### 事件卡（EventCard）

- 花费 **1 政治点数（PP）** 可以从本国牌堆随机抽一张
- 每国有自己的牌堆 = 本国事件卡 + 3 张公共事件卡
- 牌堆抽空后自动重洗
- 效果五花八门，例如：
  - 直接改变 PP 或民心值
  - 给某个单位永久加攻击力
  - 触发特殊标志（如本小回合两国禁止互攻）
  - 某些卡需要玩家**额外点击单位或地块**才能确定效果目标

### 5.6 AI 系统

`src/core/ai_service.py` 实现了一套基于规则的 AI：

1. **找边境省**：优先找己方与敌方交界的格子，距离越近优先级越高
2. **行军**：把边境格子上的部队向最近的敌方目标移动
3. **战斗**：移动完成后，检查相邻格子是否有敌方单位，如果攻防比划算就发起进攻
4. **征兵**：若某边境格子兵力不足，且 PP 够用，就在该格补充单位
5. **事件卡**：AI 也会在合适时机抽取事件卡并自动选择目标

### 5.7 摄像机（Camera）

地图比屏幕大，`src/core/camera.py` 实现了摄像机功能：

- **拖拽**：鼠标中键/右键按住拖动地图
- **缩放**：滚轮缩放，实质上是改变 `hex_side`（格子边长），所有格子坐标同步重算
- **视口裁剪**：只绘制摄像机可见范围内的格子，提高性能

### 5.8 分数系统

`src/core/score_manager.py` 负责分数计算：

- **重要城池**（如洛阳 5 分、成都 5 分、建业 5 分）对应 `Province.victory_point`
- **普通格子**占领后各得 0.5 分
- 每小回合结束时统计各国当前占领格子的总分值
- 游戏结束时展示分数榜

---

<a id="六游戏机制实现"></a>

## 六、游戏机制实现

### 整体数据流（以"玩家点击格子发动进攻"为例）

```text
用户鼠标点击
    ↓
PlayingInputService.handle_click()   ← 判断点击了什么（格子？按钮？）
    ↓
GameApp 判断当前选中状态：
  若已选择己方单位 → 点击的是敌方格子？
    ↓
CombatFlowService.begin_combat()     ← 发起战斗流程
    ↓
combat.get_ratio_column()            ← 计算攻防比
combat.resolve_combat()              ← 投骰子查表
    ↓
CombatResolutionService.apply()      ← 应用战斗结果（扣血、退兵）
    ↓
GameplayRenderService.draw()         ← 重新绘制地图和战斗动画
    ↓
InfoPanel.show_message()             ← 右侧面板显示战斗结果文字
```

### 资源加载流程

游戏启动时（`GameApp.__init__`），`AssetBuildService` 会统一加载所有资源：

1. 读取 `kingdoms.json` → 构建 `KingdomRepository`
2. 读取 `units.json` → 构建 `UnitRepository`（同时加载图片）
3. 读取 `cards.json` / `event_cards.json` → 构建卡牌仓库
4. 读取 `definitions.csv` → 构建 `MapManager`（初始化所有 `Province`）
5. 读取字体、UI 图片等

---

<a id="七数据配置说明"></a>

## 七、数据配置说明

游戏的大量参数写在 `assets/data/` 下的 JSON 文件中，**无需修改代码**就能调整游戏数值。

### `kingdoms.json`（国家）

```json
[
  { "id": "WEI", "name": "魏", "color": "blue" },
  { "id": "SHU", "name": "蜀", "color": "green" },
  { "id": "WU",  "name": "吴", "color": "red"  }
]
```

### `units.json`（兵种）

```json
[
  {
    "type": "infantry",
    "move": 2,      ← 每回合移动力
    "attack": 3,    ← 参与战斗时的攻击力
    "defense": 3,   ← 参与战斗时的防御力
    "range": 1,     ← 攻击射程（1=近战）
    "country": null ← null 表示三国通用，否则填 "WEI"/"SHU"/"WU"
  }
]
```

### `definitions.csv`（地图格子）

每行代表一个六边形格子，包含：ID、名称、归属国、地形、防御值、胜利点数、逻辑坐标等。

### `settings.py`（全局配置）

```python
SETTINGS = Settings(
    fps=60,              ← 游戏帧率
    window_title="三足鼎立",
    borderless=False,    ← 是否无边框窗口
    ...
)

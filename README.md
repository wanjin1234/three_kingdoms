# 三国游戏开发说明文档

## 一、文件架构：

``` text
three_kingdoms/
├── .gitignore              <-- 【核心】git忽略文件
├── README.md               <-- 项目说明书
├── requirements.txt        <-- 依赖库列表
├── main.py                 <-- 【入口】游戏的启动文件
├── settings.py             <-- 【配置】全局变量（屏幕大小、FPS、颜色）
├── assets/                 <-- 【资源库】所有非代码的东西
│   ├── map/                <-- 钢铁雄心的灵魂：地图
│   │   ├── visual.png      <-- 给玩家看的高清地图
│   │   ├── provinces.bmp   <-- 给代码看的省份色块图
│   │   └── definitions.csv <-- 省份数据表（ID, 名字, 地形）
│   ├── graphics/           <-- 图片
│   │   ├── units/          <-- 兵牌/Sprite
│   │   ├── flags/          <-- 国旗
│   │   └── ui/             <-- 界面按钮、面板背景
│   ├── fonts/              <-- 字体
│   └── data/               <-- 游戏数值
│       ├── kingdoms.json   <-- 国家定义
│       └── units.json      <-- 兵种属性
└── src/                    <-- 【源代码】所有逻辑代码
    ├── __init__.py
    ├── core/               <-- 核心引擎
    │   ├── __init__.py
    │   ├── app.py          <-- 游戏主循环类
    │   ├── camera.py       <-- 摄像机控制
    │   └── events.py       <-- 输入事件处理
    ├── map/                <-- 地图系统
    │   ├── __init__.py
    │   ├── map_manager.py  <-- 地图加载与渲染
    │   └── province.py     <-- 省份类
    ├── game_objects/       <-- 游戏对象
    │   ├── __init__.py
    │   ├── unit.py         <-- 军队类
    │   └── kingdom.py      <-- 国家类
    └── ui/                 <-- 界面系统
        ├── __init__.py
        └── panels.py       <-- 信息面板
```

---

## 二、开发流程：（Gemini说的）

这是一个非常典型的**小型团队协作（2-5人）**场景。

针对你们现在的仓库状态（只有 `master` 和 `game` 两个分支），我建议采用一种简化版的 **Git Flow 工作流**。

我们可以把这两个分支想象成**“展厅”**和**“车间”**。

### （一）两个分支的定义与职责

#### 1. `master` 分支：【展厅】（稳定版）
*   **状态**：**必须永远是可以运行的**。
*   **内容**：经过测试、没有严重 BUG 的版本。
*   **更新频率**：低（例如每周末合并一次，或者完成一个大里程碑时）。
*   **谁来改**：通常**不允许直接 Push 代码**到 master。只能从 `game` 分支合并过来。
*   **作用**：如果有老师检查作业，或者要发给朋友玩，就给这个分支的代码。

#### 2. `game` 分支：【车间】（开发版）
*   **状态**：**基本可运行，但允许有小 Bug**。
*   **内容**：大家写好的最新功能都汇聚到这里。
*   **更新频率**：高（每天都有更新）。
*   **谁来改**：这是所有人的代码汇合点。
*   **作用**：这是你们日常开发的基准。你每天开工前，都要先从这里拉取（Pull）最新代码。

### （二）协作流程：手把手教你干活

假设你是负责**“绘制地图”**的，你的队友是负责**“兵种逻辑”**的。你们应该这样配合：

#### 第一步：初始化（仅需做一次）
由 Leader（或者技术最好的那个人）在 `game` 分支上把“地基”打好：
1.  建立 `src`, `assets` 文件夹。
2.  **必须**上传 `.gitignore` 文件（防止垃圾文件冲突）。
3.  上传一个最简单的 `main.py`（哪怕只能打印个 "Hello Three Kingdoms"）。
4.  把这些推送到 GitHub 的 `game` 分支。

#### 第二步：你的日常工作循环（重点！）

不要直接在 `game` 分支上写代码！万一你写挂了，队友拉下来一跑就报错，会影响大家进度。

**请遵循“开小差”原则（Feature Branch Workflow）：**

**1. 开工前，先同步**
每天早上坐下，先切到 `game` 分支，把云端最新的代码拉下来：
```bash
git checkout game
git pull origin game
```

**2. 开个“小分支”干活**
假设你要写地图加载功能，就从 `game` 分支切出一个临时的任务分支：
```bash
git checkout -b feature/map_rendering
```
*现在你在这个分支上随便改，就算把代码改爆炸了，也不会影响队友。*

**3. 写代码、提交**
你修改了 `map.py`，画出了地图。
```bash
git add .
git commit -m "完成地图的基础加载功能"
```

**4. 再次同步（防冲突关键一步）**
在你准备上传之前，队友可能已经上传了新代码。为了防止冲突，你先切回 `game` 拉一下：
```bash
git checkout game
git pull origin game  # 看看有没有新东西
git checkout feature/map_rendering  # 切回你的分支
git merge game        # 把队友的新东西合并到你的任务里
```
*如果有冲突，IDE（VS Code/PyCharm）会提示你解决。解决完后，你的代码就是最新且包含你功能的代码。*

**5. 上传并合并**
把你的任务分支推送到 GitHub：
```bash
git push origin feature/map_rendering
```
然后，去 GitHub 网页上，点击 **"New Pull Request"**：
*   **From**: `feature/map_rendering`
*   **To**: `game`
*   点击 **Merge**。

**6. 删除小分支**
合并成功后，这个临时分支就没用了，删掉它，深藏功与名。

### （三）具体的代码/素材分工（针对 Pygame 战棋）

为了避免大家同时改同一个文件（这是冲突之源），建议你们按**模块**拆分文件。

**一个简化的文件结构的例子，便于讲解：**

```text
three_kingdoms/
├── main.py             <-- 【入口】只写几行代码，负责初始化和主循环
├── settings.py         <-- 【配置】屏幕大小、帧率、颜色定义
├── assets/             <-- 【素材】所有图片放这里
├── src/
│   ├── map_system.py   <-- 【你负责】地图加载、坐标转换、摄像机逻辑
│   ├── unit_system.py  <-- 【队友A负责】兵种定义、移动逻辑
│   ├── ui_system.py    <-- 【队友B负责】按钮、菜单绘制
│   └── game_state.py   <-- 【核心】管理当前是"玩家回合"还是"敌人回合"
```

**协作守则：**
1.  **你只改 `map_system.py`**，尽量别碰 `unit_system.py`。
2.  **`main.py` 大家都要用**，所以改动要谨慎。尽量只在里面调用函数，比如 `map_manager.draw()`，不要在里面写长逻辑。
3.  **素材命名要规范**：
    *   ✅ `map_grass.png`, `unit_cavalry_red.png`
    *   ❌ `1.png`, `test.jpg`, `新建文件夹`

---

## 三、命名规范：（Gemini说的）

既然你们使用的是 **Python (Pygame)** 进行开发，最标准、最不容易出锅的方案就是严格遵守 Python 官方的 **PEP 8 规范**。

为了避免团队里出现“一个叫 `MapManager`，一个叫 `map_loader`，还有一个叫 `loadMap`”这种混乱场面，请把下面这套**《代码命名宪法》**发到你们的群里，强制执行。

### （一）仓库与文件夹 (Repository & Directories)

**规则：全小写 + 下划线 (`snake_case`)**
这是为了兼容所有操作系统（Windows 不区分大小写，Linux 区分，混用大写容易导致 git 找不到文件）。

*   **GitHub 仓库名**：`three_kingdoms` (或者 `three-kingdoms`)
*   **根目录文件夹**：`three_kingdoms_project`
*   **代码包目录**：`src`, `assets`, `core`, `map_system`
    *   ✅ 正确：`src/game_objects/`
    *   ❌ 错误：`src/GameObjects/` (像 C#)
    *   ❌ 错误：`src/gameobjects/` (太长难读)

### （二）Python 代码文件 (Files)

**规则：全小写 + 下划线 (`snake_case`)**
文件名应该尽量短，但要能看懂。

*   ✅ 正确：`main.py`
*   ✅ 正确：`province_manager.py`
*   ✅ 正确：`unit_ai.py`
*   ❌ 错误：`ProvinceManager.py` (这是 Java/C# 风格)
*   ❌ 错误：`util.py` (太笼统，不知道里面是啥，建议用 `math_utils.py`)

### （三） 类 (Classes) —— 唯一的“大写”特权

**规则：大驼峰命名法 (`PascalCase`)**
首字母大写，每个单词首字母都大写，**不加下划线**。

*   ✅ 正确：`GameMap`
*   ✅ 正确：`InfantryUnit` (步兵单位)
*   ✅ 正确：`Province` (省份)
*   ❌ 错误：`game_map` (这是变量名风格)
*   ❌ 错误：`CMap` (不要加 C 前缀，那是 C++)

### （四）变量与函数 (Variables & Functions)

**规则：全小写 + 下划线 (`snake_case`)**
这是 Python 最核心的风格。

*   **普通变量**：
    *   ✅ 正确：`current_hp`, `player_score`, `selected_province`
    *   ❌ 错误：`currentHp` (小驼峰是 JS/C# 风格), `PlayerScore`
*   **函数/方法**：
    *   ✅ 正确：`calculate_damage()`, `draw_map()`, `get_movement_cost()`
    *   ❌ 错误：`DrawMap()`
*   **私有变量/方法**（仅在类内部使用，不希望外部调用）：
    *   **规则**：前面加一个下划线 `_`
    *   ✅ 正确：`_load_texture()`, `_internal_id`
*   **布尔值 (Boolean)**：
    *   **建议**：加上 `is_`, `has_`, `can_` 前缀，读起来像英语句子。
    *   ✅ 正确：`is_alive`, `has_moved`, `can_attack`
    *   ❌ 错误：`alive`, `move`, `attack` (容易和函数名混淆)

### （五）常量 (Constants)

**规则：全大写 + 下划线 (`UPPER_CASE`)**
通常放在 `settings.py` 里，表示游戏运行时**绝对不许改**的数值。

*   ✅ 正确：`SCREEN_WIDTH = 1280`
*   ✅ 正确：`MAX_UNIT_COUNT = 100`
*   ✅ 正确：`COLOR_WEI_BLUE = (50, 50, 255)`

### （六）资源素材 (Assets) —— 重点！

做游戏素材极多，如果不规范，后期找图会疯掉。
**规则：`类别_具体名_状态.扩展名` (全小写)**

*   **图片 (Images)**：
    *   ✅ 正确：`btn_start_normal.png` (开始按钮-普通态)
    *   ✅ 正确：`btn_start_hover.png` (开始按钮-悬停态)
    *   ✅ 正确：`unit_cavalry_red_idle.png` (骑兵-红方-待机)
    *   ✅ 正确：`map_terrain_mountain.png`
    *   ❌ 错误：`1.png`, `bg.jpg`, `曹操.png` (尽量别用中文，虽然 Pygame 支持，但在某些打包工具有坑)

### （七）Git 分支 (Branches)

**规则：`类型/描述` (全小写)**

*   **功能开发**：`feature/xxx`
    *   例子：`feature/map-rendering` (地图渲染)
    *   例子：`feature/add-cavalry` (添加骑兵)
*   **修复 Bug**：`bugfix/xxx`
    *   例子：`bugfix/fix-crash-on-start`
*   **整理代码**：`refactor/xxx`
    *   例子：`refactor/directory-structure`

### 🚀 总结一张表 (Cheat Sheet)

把这张表置顶到你们的 GitHub Readme 或者聊天群里：

| 对象             | 命名风格    | 例子             | 备注           |
| :--------------- | :---------- | :--------------- | :------------- |
| **文件夹**       | snake_case  | `game_objects/`  | 全小写         |
| **Python文件**   | snake_case  | `main_menu.py`   | 全小写         |
| **类 (Class)**   | PascalCase  | `CombatSystem`   | **首字母大写** |
| **函数 (Func)**  | snake_case  | `get_position()` | 动词开头       |
| **变量 (Var)**   | snake_case  | `enemy_list`     | 名词           |
| **常量 (Const)** | UPPER_CASE  | `FPS_LIMIT`      | 全大写         |
| **私有成员**     | _snake_case | `_recalculate()` | 下划线开头     |
| **图片素材**     | snake_case  | `icon_sword.png` | `前缀_名.png`  |

**特别提醒：**
在 Python 里，**千万不要**使用匈牙利命名法（比如 `iCount`, `strName`, `bIsDead`）。Python 是动态类型语言，这种写法非常“土”且不被推荐。直接写 `count`, `name`, `is_dead` 即可。

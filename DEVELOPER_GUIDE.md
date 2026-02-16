# 卡牌系统开发者指南

## 目录
1. [系统架构](#系统架构)
2. [添加新卡牌](#添加新卡牌)
3. [实现卡牌效果](#实现卡牌效果)
4. [自定义 UI](#自定义-ui)
5. [常见问题](#常见问题)

---

## 系统架构

```
┌─────────────────────────────────────────┐
│         GameApp (游戏主程序)              │
├─────────────────────────────────────────┤
│                                          │
│  ┌────────────────────────────────┐    │
│  │    CardManager (国家级管理)     │    │
│  │  - 追踪卡牌状态                 │    │
│  │  - 管理可用/已用卡牌           │    │
│  └────────────────────────────────┘    │
│             ↓                           │
│  ┌────────────────────────────────┐    │
│  │  CardRepository (卡牌仓库)      │    │
│  │  - 加载卡牌定义                 │    │
│  │  - 提供卡牌查询接口             │    │
│  └────────────────────────────────┘    │
│             ↓                           │
│  ┌────────────────────────────────┐    │
│  │  cards.json (数据文件)          │    │
│  │  - 定义所有卡牌                 │    │
│  └────────────────────────────────┘    │
│                                          │
│  ┌────────────────────────────────┐    │
│  │   CardPanel (UI 组件)           │    │
│  │  - 显示卡牌列表                 │    │
│  │  - 处理用户交互                 │    │
│  └────────────────────────────────┘    │
│                                          │
└─────────────────────────────────────────┘
```

### 数据流

```
加载游戏
  ↓
CardRepository 读取 cards.json
  ↓
选择国家
  ↓
CardManager(repo, country) 初始化
  ↓
GameApp._update_card_panel() 调用
  ↓
CardPanel.set_available_cards() 显示卡牌
  ↓
玩家交互（点击/悬停/Enter）
  ↓
CardPanel 更新选择状态
  ↓
GameApp._play_selected_card() 处理使用
  ↓
CardManager.use_card() 标记已用
  ↓
GameApp._update_card_panel() 刷新显示
```

---

## 添加新卡牌

### 步骤 1: 编辑 cards.json

编辑 `assets/data/cards.json`，添加新卡牌定义：

```json
{
  "id": "card_example_id",
  "name": "示例卡牌",
  "country": "SHU",
  "description": "这是一张示例卡牌的效果描述",
  "category": "offensive"
}
```

**字段说明:**
- `id`: 唯一标识符（建议格式 `card_类别_名称_国家`）
- `name`: 用户可见的卡牌名称
- `country`: 所属国家 (`SHU`, `WU`, `WEI`)
- `description`: 卡牌效果的详细描述
- `category`: 分类类型
  - `offensive`: 进攻类
  - `defensive`: 防守类
  - `summon`: 召唤类
  - `buff`: 增益类

### 步骤 2: 测试加载

```python
from src.game_objects.card import CardRepository
from settings import SETTINGS

repo = CardRepository(SETTINGS.cards_file)
shu_cards = repo.get_cards_by_country("SHU")
for card in shu_cards:
    print(f"{card.name}: {card.description}")
```

---

## 实现卡牌效果

### 在 GameApp 中添加效果处理

编辑 `src/core/app.py` 中的 `_play_selected_card()` 方法：

```python
def _play_selected_card(self) -> None:
    """打出选中的卡牌"""
    # ... 现有代码 ...
    
    # 使用卡牌
    card_def = self.card_repository.get_definition(selected_card_id)
    if card_def:
        # 标记卡牌为已使用
        self.card_manager.use_card(selected_card_id)
        
        # ========== 添加效果处理 ==========
        self._apply_card_effect(card_def)  # 调用新方法
        # =================================
        
        # ... 其余代码 ...
```

### 实现效果处理方法

```python
def _apply_card_effect(self, card_def: CardDefinition) -> None:
    """应用卡牌效果"""
    
    if card_def.id == "card_zhenjing_huaxia_shu":
        # 威震华夏效果实现
        self._apply_zhenjing_huaxia()
    
    elif card_def.id == "card_qilin_qishu":
        # 七擒七纵效果实现
        self._apply_qilin_qishu()
    
    elif card_def.id == "card_kongcheng_mouce":
        # 空城妙计效果实现
        self._apply_kongcheng_mouce()
    
    # ... 其他卡牌 ...
    
    self.info_panel.show_message(f"技能卡效果生效: {card_def.name}", duration=2.0)


def _apply_zhenjing_huaxia(self) -> None:
    """威震华夏：河岸战斗优势"""
    # 实现逻辑：
    # 1. 记录卡牌已激活
    # 2. 标记本轮战斗
    # 3. 在战斗时调用 COMBAT_TABLE 时应用修正
    pass


def _apply_qilin_qishu(self) -> None:
    """七擒七纵：获得无当飞军"""
    # 实现逻辑：
    # 1. 选择部署地点
    # 2. 生成无当飞军单位
    # 3. 添加到地图
    pass


def _apply_kongcheng_mouce(self) -> None:
    """空城妙计：保护格子"""
    # 实现逻辑：
    # 1. 选择目标格子
    # 2. 标记为受保护状态
    # 3. 阻止敌方进攻
    pass
```

### 集成到战斗系统

卡牌效果需要集成到 `src/core/combat.py`：

```python
def resolve_combat(...):
    """战斗解决"""
    # ... 现有代码 ...
    
    # 检查威震华夏效果
    if app.active_card_effects.get("zhenjing_huaxia"):
        # 修改战斗判定
        ratio_col = max(ratio_col - 1, 0)  # 向左移动一列
    
    # ... 其余逻辑 ...
```

---

## 自定义 UI

### 修改卡牌显示样式

编辑 `src/ui/info_panel.py` 中的 `CardPanel.draw()` 方法：

```python
def draw(self, surface: pg.Surface) -> None:
    # ... 现有代码 ...
    
    for card in self.available_cards:
        # 自定义颜色
        if card.category == "offensive":
            bg_color = pg.Color(255, 200, 200)  # 浅红
        elif card.category == "defensive":
            bg_color = pg.Color(200, 200, 255)  # 浅蓝
        elif card.category == "summon":
            bg_color = pg.Color(255, 220, 200)  # 浅橙
        else:
            bg_color = pg.Color(240, 240, 240)  # 灰白
        
        # 绘制卡牌背景
        pg.draw.rect(surface, bg_color, card_rect)
        
        # ... 其余代码 ...
```

### 添加卡牌图片

```python
class CardPanel(BasePanel):
    def __init__(self, ...):
        # ... 现有代码 ...
        self.card_images: Dict[str, pg.Surface] = {}
    
    def load_card_image(self, card_id: str, image_path: Path) -> None:
        """加载卡牌图片"""
        try:
            img = pg.image.load(image_path)
            self.card_images[card_id] = pg.transform.scale(img, (80, 100))
        except Exception as e:
            logger.warning(f"Failed to load card image: {e}")
    
    def draw(self, surface: pg.Surface) -> None:
        # ... 现有代码 ...
        
        # 绘制卡牌图片
        if card.id in self.card_images:
            surface.blit(self.card_images[card.id], 
                        (card_rect.x + 5, card_rect.y + 5))
```

### 实现卡牌详情面板

```python
class CardDetailPanel(BasePanel):
    """卡牌详情面板"""
    
    def show_card(self, card_def: CardDefinition) -> None:
        """显示卡牌详细信息"""
        self.current_card = card_def
    
    def draw(self, surface: pg.Surface) -> None:
        if not self.current_card:
            return
        
        content_y = self.draw_background_and_border(surface)
        
        # 绘制卡牌标题
        title_surf = self.font.render(self.current_card.name, True, 
                                     pg.Color("darkred"))
        surface.blit(title_surf, (self.rect.left + 10, content_y))
        
        content_y += title_surf.get_height() + 10
        
        # 绘制类别
        category_text = f"类别: {self.current_card.category}"
        category_surf = self._get_font(12).render(category_text, True, 
                                                  pg.Color("gray"))
        surface.blit(category_surf, (self.rect.left + 10, content_y))
        
        # ... 绘制详细描述 ...
```

---

## 常见问题

### Q1: 如何添加新国家的卡牌？

在 `assets/data/cards.json` 中，将卡牌的 `country` 字段设置为新国家代码，比如 `"JIN"`。系统会自动加载。

### Q2: 如何修改卡牌效果信息？

直接编辑 `assets/data/cards.json` 中对应卡牌的 `description` 字段。修改会在下次游戏启动时生效。

### Q3: 如何限制卡牌的使用次数？

修改 `CardState` 类：

```python
@dataclass
class CardState:
    card_id: str
    is_used: bool = False
    usage_count: int = 0  # 新增
    max_usage: int = 1    # 新增
    
    def can_use(self) -> bool:
        return self.usage_count < self.max_usage
```

### Q4: 如何实现卡牌动画？

使用 pygame 的 animation 模块或自定义帧动画：

```python
def draw_card_usage_animation(self, surface, duration=0.5):
    """绘制卡牌使用动画"""
    elapsed = pygame.time.get_ticks() - self.animation_start_time
    progress = min(elapsed / (duration * 1000), 1.0)
    
    # 使用 progress 计算透明度或缩放
    alpha = int(255 * (1 - progress))
    
    card_surf = self.card_images[self.selected_card_id].copy()
    card_surf.set_alpha(alpha)
    surface.blit(card_surf, self.card_rects[self.selected_card_id])
```

### Q5: 如何跨回合保存卡牌状态？

实现持久化方法：

```python
def save_card_state(self, filename: str) -> None:
    """保存卡牌状态"""
    state = {
        'country': self.card_manager.country,
        'used_cards': [
            card_id for card_id, state in self.card_manager.cards.items()
            if state.is_used
        ]
    }
    with open(filename, 'w') as f:
        json.dump(state, f)

def load_card_state(self, filename: str) -> None:
    """加载卡牌状态"""
    with open(filename, 'r') as f:
        state = json.load(f)
    
    for card_id in state['used_cards']:
        self.card_manager.use_card(card_id)
```

### Q6: 卡牌内容太多，如何实现滚动？

```python
class CardPanel(BasePanel):
    def __init__(self, ...):
        # ... 现有代码 ...
        self.scroll_offset = 0
        self.cards_per_view = 5
    
    def scroll_up(self) -> None:
        self.scroll_offset = max(0, self.scroll_offset - 1)
    
    def scroll_down(self) -> None:
        max_scroll = max(0, len(self.available_cards) - self.cards_per_view)
        self.scroll_offset = min(self.scroll_offset + 1, max_scroll)
    
    def draw(self, surface: pg.Surface) -> None:
        # ... 绘制代码 ...
        
        # 只绘制可见范围内的卡牌
        for i in range(self.scroll_offset, 
                      min(self.scroll_offset + self.cards_per_view,
                          len(self.available_cards))):
            # 绘制 self.available_cards[i]
            pass
```

---

## 最佳实践

1. **卡牌 ID 命名规范**
   ```
   card_[分类]_[名称拼音简写]_[国家]
   例: card_offensive_zhenjing_shu
   ```

2. **效果实现分层**
   - 数据层：JSON 定义
   - 管理层：CardManager 状态跟踪
   - 业务层：_apply_card_effect() 实现
   - 交互层：UI 事件处理

3. **错误处理**
   ```python
   try:
       card_def = self.card_repository.get_definition(card_id)
       if not card_def:
           self.info_panel.show_message("卡牌不存在")
           return
       
       # 应用效果
       self._apply_card_effect(card_def)
   
   except Exception as e:
       logger.error(f"Card usage error: {e}")
       self.info_panel.show_message("卡牌使用出错")
   ```

4. **日志记录**
   ```python
   logger.info(f"Card selected: {card_def.name} (ID: {card_id})")
   logger.info(f"Card used: {card_def.name}")
   logger.debug(f"Card effect applied with result: {effect_result}")
   ```

---

## 扩展资源

- 📖 [游戏规则 v1.4.2](游戏规则v1.4.2.docx)
- 📘 [API 文档](IMPLEMENTATION_SUMMARY.md)
- 🚀 [快速参考](CARD_QUICK_REF.md)
- 🧪 [测试套件](test_integration.py)

---

**文档版本**: v1.0  
**最后更新**: 2026-02-15

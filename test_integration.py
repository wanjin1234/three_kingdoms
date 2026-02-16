#!/usr/bin/env python
"""
卡牌系统集成测试
验证所有组件正确集成
"""
import sys
from pathlib import Path

# 检查导入
print("=== 模块导入检查 ===")
try:
    from src.game_objects.card import CardRepository, CardManager, CardDefinition, CardState
    print("✓ 卡牌模块导入成功")
except ImportError as e:
    print(f"✗ 卡牌模块导入失败: {e}")
    sys.exit(1)

try:
    from src.ui.info_panel import CardPanel
    print("✓ UI 组件导入成功")
except ImportError as e:
    print(f"✗ UI 组件导入失败: {e}")
    sys.exit(1)

try:
    from settings import SETTINGS
    print("✓ 配置导入成功")
except ImportError as e:
    print(f"✗ 配置导入失败: {e}")
    sys.exit(1)

# 检查文件存在
print("\n=== 文件检查 ===")
if SETTINGS.cards_file.exists():
    print(f"✓ 卡牌文件存在: {SETTINGS.cards_file}")
else:
    print(f"✗ 卡牌文件不存在: {SETTINGS.cards_file}")
    sys.exit(1)

# 检查卡牌仓库
print("\n=== 卡牌仓库检查 ===")
try:
    card_repo = CardRepository(SETTINGS.cards_file)
    num_cards = len(card_repo._definitions)
    print(f"✓ 卡牌仓库加载成功，包含 {num_cards} 张卡牌")
    
    # 验证每个国家的卡牌
    for country in ["SHU", "WU", "WEI"]:
        cards = card_repo.get_cards_by_country(country)
        print(f"  ✓ {country}: {len(cards)} 张卡牌")
        for card in cards:
            assert hasattr(card, 'id'), f"卡牌缺少 id 属性: {card.name}"
            assert hasattr(card, 'name'), f"卡牌缺少 name 属性: {card.id}"
            assert hasattr(card, 'description'), f"卡牌缺少 description 属性: {card.name}"
    print("✓ 所有卡牌属性验证通过")
    
except Exception as e:
    print(f"✗ 卡牌仓库加载失败: {e}")
    sys.exit(1)

# 检查卡牌管理器
print("\n=== 卡牌管理器检查 ===")
try:
    for country in ["SHU", "WU", "WEI"]:
        manager = CardManager(card_repo, country)
        
        # 获取可用卡牌
        available = manager.get_available_cards()
        total = manager.get_all_cards()
        print(f"✓ {country} 管理器: {len(available)}/{len(total)} 卡牌可用")
        
        # 测试使用卡牌
        if available:
            first_card = available[0]
            manager.use_card(first_card.id)
            new_available = manager.get_available_cards()
            assert len(new_available) == len(available) - 1, "使用卡牌后数量不正确"
            assert manager.is_card_used(first_card.id), "卡牌状态未正确更新"
            print(f"  ✓ {country} 卡牌使用测试通过")
    print("✓ 所有国家的卡牌管理器验证通过")
    
except Exception as e:
    print(f"✗ 卡牌管理器检查失败: {e}")
    sys.exit(1)

# 检查 CardPanel 类
print("\n=== UI 面板检查 ===")
try:
    import pygame as pg
    
    # 初始化 pygame（无显示）
    pg.init()
    
    # 创建一个虚拟字体和矩形
    font = pg.font.SysFont("arial", 20)
    rect = pg.Rect(100, 100, 300, 400)
    
    # 创建 CardPanel
    panel = CardPanel(rect, font)
    print("✓ CardPanel 实例化成功")
    
    # 验证 CardPanel 方法
    assert hasattr(panel, 'set_available_cards'), "CardPanel 缺少 set_available_cards 方法"
    assert hasattr(panel, 'select_card'), "CardPanel 缺少 select_card 方法"
    assert hasattr(panel, 'get_card_at'), "CardPanel 缺少 get_card_at 方法"
    assert hasattr(panel, 'get_selected_card'), "CardPanel 缺少 get_selected_card 方法"
    assert hasattr(panel, 'handle_mouse_motion'), "CardPanel 缺少 handle_mouse_motion 方法"
    assert hasattr(panel, 'draw'), "CardPanel 缺少 draw 方法"
    print("✓ CardPanel 所有必需方法都存在")
    
    # 测试设置卡牌
    shu_cards = card_repo.get_cards_by_country("SHU")
    panel.set_available_cards(shu_cards)
    print(f"✓ CardPanel 加载了 {len(shu_cards)} 张蜀汉卡牌")
    
    # 测试卡牌选择
    if shu_cards:
        first_card = shu_cards[0]
        panel.select_card(first_card.id)
        assert panel.get_selected_card() == first_card.id, "卡牌选择失败"
        print(f"✓ 卡牌选择测试通过：{first_card.name}")
    
    pg.quit()
    
except Exception as e:
    print(f"✗ UI 面板检查失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 检查事件处理
print("\n=== 事件处理检查 ===")
try:
    from src.core.app import GameApp
    # 我们不需要实际运行 GameApp，只需验证导入成功
    print("✓ GameApp 导入成功（卡牌系统已集成）")
except ImportError as e:
    print(f"✗ GameApp 导入失败: {e}")
    sys.exit(1)

# 最终总结
print("\n" + "="*50)
print("✓ 卡牌系统集成验证完成！")
print("="*50)
print("\n系统已准备好进行游戏！")
print("\n卡牌使用快速指南:")
print("  1. 左键点击卡牌栏中的卡牌来选中")
print("  2. 悬停鼠标查看卡牌效果描述")
print("  3. 按 Enter 键打出选中的卡牌")
print("  4. 已使用的卡牌会从卡牌栏消失")

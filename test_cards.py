#!/usr/bin/env python
"""
卡牌系统测试脚本
"""
from pathlib import Path
from src.game_objects.card import CardRepository, CardManager

# 测试卡牌仓库
cards_file = Path("assets/data/cards.json")
card_repo = CardRepository(cards_file)

print("=== 卡牌仓库测试 ===")
print(f"总卡牌数: {len(card_repo._definitions)}")

# 测试每个国家的卡牌
for country in ["SHU", "WU", "WEI"]:
    cards = card_repo.get_cards_by_country(country)
    print(f"\n{country} 的卡牌:")
    for card in cards:
        print(f"  - {card.name} ({card.id})")
        print(f"    类别: {card.category}")
        print(f"    效果: {card.description}")

# 测试卡牌管理器
print("\n=== 卡牌管理器测试 ===")
shu_manager = CardManager(card_repo, "SHU")

print(f"蜀汉可用卡牌数: {len(shu_manager.get_available_cards())}")

# 测试使用卡牌
available_cards = shu_manager.get_available_cards()
if available_cards:
    first_card = available_cards[0]
    print(f"\n使用卡牌: {first_card.name}")
    shu_manager.use_card(first_card.id)
    
    print(f"使用后可用卡牌数: {len(shu_manager.get_available_cards())}")
    print(f"卡牌'{first_card.name}'是否已使用: {shu_manager.is_card_used(first_card.id)}")

print("\n✓ 测试完成!")

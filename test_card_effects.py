"""
卡牌效果测试 - 验证七擒七纵、威震华夏和火烧连营的功能
"""
from src.game_objects.card_effects import CardEffectManager

# 测试CardEffectManager
effect_mgr = CardEffectManager()

print("=== 卡牌效果激活测试 ===\n")

# 测试应用七擒七纵到格子
print("测试七擒七纵（summon类卡牌）:")
province_id = "province_001"
result = effect_mgr.apply_card_effect("card_qilin_qishu", "七擒七纵", province_id, "SHU")
print(f"  应用到格子 {province_id}: {result}")
effect = effect_mgr.get_effect(province_id)
if effect:
    print(f"  格子上的效果: protected={effect.protected}, card_name={effect.card_name}")

# 测试应用威震华夏到有河流的格子
print("\n测试威震华夏（offensive类，需要河流相邻）:")
province_id2 = "province_002"
result = effect_mgr.apply_card_effect("card_zhenjing_huaxia_shu", "威震华夏", province_id2, "SHU")
print(f"  应用到格子 {province_id2}: {result}")
effect = effect_mgr.get_effect(province_id2)
if effect:
    print(f"  格子上的效果: river_edge_bonus={effect.river_edge_bonus}, card_name={effect.card_name}")

# 测试火烧连营激活
print("\n测试火烧连营（offensive类，直接激活）:")
result = effect_mgr.activate_offensive_card("card_huoshao_lianying")
print(f"  激活结果: {result}")
print(f"  是否激活: {effect_mgr.is_offensive_card_active('card_huoshao_lianying')}")

# 测试刮目相看
print("\n测试刮目相看（summon类卡牌）:")
province_id3 = "province_003"
result = effect_mgr.apply_card_effect("card_guanmu_xiangkan", "刮目相看", province_id3, "WU")
print(f"  应用到格子 {province_id3}: {result}")

# 测试效果检查
print("\n=== 效果检查测试 ===\n")
print(f"格子{province_id}有效果: {effect_mgr.has_effect(province_id)}")
print(f"格子{province_id2}有效果: {effect_mgr.has_effect(province_id2)}")
print(f"格子{province_id3}有效果: {effect_mgr.has_effect(province_id3)}")
print(f"已激活的offensive卡牌: {effect_mgr.active_offensive_cards}")

# 测试清除效果
print("\n=== 清除效果测试 ===\n")
effect_mgr.clear_all_effects()
print(f"清除后格子{province_id}有效果: {effect_mgr.has_effect(province_id)}")
print(f"清除后激活的offensive卡牌: {effect_mgr.active_offensive_cards}")

print("\n✓ 卡牌效果测试完成!")

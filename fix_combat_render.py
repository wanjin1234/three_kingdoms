import re

with open("src/core/app.py", encoding="utf-8") as f:
    content = f.read()

changes = 0

# Fix 1: selecting_evt_target hint_y - remove shift-down block
old1 = """            hint_y = (top_area_h - hint_h) // 2
            # 若战斗结果正在显示，下移至其下方
            if self.combat_result_title and self.combat_result_timer != 0:
                cr_lines = self.combat_result_title.split("\\n")
                lh = font.get_height()
                cr_total_h = len(cr_lines) * lh + (len(cr_lines) - 1) * 5
                cr_start_y = max(2, top_area_h // 6 - cr_total_h // 2)
                hint_y = max(hint_y, cr_start_y + cr_total_h + 6)
            hint_x = tag_x"""
new1 = """            hint_y = top_area_h // 2 - hint_h // 2
            hint_x = tag_x"""

if old1 in content:
    content = content.replace(old1, new1, 1)
    changes += 1
    print("Fix 1 applied: removed selecting_evt_target shift-down")
else:
    print("Fix 1 FAILED: hint_y block not found")

# Fix 2: btn_y - remove shift-down block
old2 = """        btn_y = (top_area_h - btn_h) // 2

        # 若战斗结果正在显示，将按钮整体下移至战斗结果文本块下方，避免重叠
        if self.combat_result_title and self.combat_result_timer != 0:
            cr_lines = self.combat_result_title.split("\\n")
            lh = font.get_height()
            cr_total_h = len(cr_lines) * lh + (len(cr_lines) - 1) * 5
            cr_start_y = max(2, top_area_h // 6 - cr_total_h // 2)
            cr_bottom = cr_start_y + cr_total_h
            btn_y = max(btn_y, cr_bottom + 6)
        skip_w"""
new2 = """        btn_y = top_area_h // 2 - btn_h // 2
        skip_w"""

if old2 in content:
    content = content.replace(old2, new2, 1)
    changes += 1
    print("Fix 2 applied: removed btn_y shift-down")
else:
    print("Fix 2 FAILED: btn_y block not found")

with open("src/core/app.py", encoding="utf-8", mode="w") as f:
    f.write(content)

print(f"Done: {changes}/2 fixes applied")

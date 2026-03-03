"""
历史检查脚本（保留用于追溯）。

注意：该文件用于一次性问题定位记录，不应作为常规开发流程的一部分。
"""

with open("src/core/app.py", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "_render_draw_event_btn" in line and "def " in line:
        print(f"Found at line {i + 1}")
        for j in range(i, min(i + 60, len(lines))):
            print(f"{j + 1}: {repr(lines[j])}")
        break

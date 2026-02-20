with open("src/core/app.py", encoding="utf-8") as f:
    lines = f.readlines()

# Find the start marker line
for i, line in enumerate(lines):
    if "画战斗结果 (Top UI)" in line:
        print(f"Found start at line {i + 1}: {repr(line)}")
        # Print surrounding 80 lines
        for j in range(i, min(i + 80, len(lines))):
            print(f"{j + 1}: {repr(lines[j])}")
        break

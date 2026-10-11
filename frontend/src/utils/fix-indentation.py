from pathlib import Path

def fix_indent(file: Path, indent: int = 4) -> None:
    with open(file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    level = 0
    pending_assign = False
    matching = {")": "(", "]": "[", "}": "{"}

    for line in lines:
        stripped = line.strip()

        if not stripped:
            new_lines.append("\n")
            continue

        # 1. Filtra delimitadores que se fecham na própria linha
        unmatched = []
        for char in stripped:
            if char in "({[":
                unmatched.append(char)
            elif char in ")]}":
                if unmatched and unmatched[-1] == matching[char]:
                    unmatched.pop()
                else:
                    unmatched.append(char)

        opens = [c for c in unmatched if c in "({["]
        closes = [c for c in unmatched if c in ")]}"]

        starts_with_close = stripped[0] in ")]}"

        if starts_with_close:
            level = max(0, level - 1)

        # 2. Se a linha anterior terminou especificamente com '=', adiciona +1 nível temporário
        effective_level = level + (1 if pending_assign and not starts_with_close else 0)

        new_lines.append(" " * (effective_level * indent) + stripped + "\n")

        # 3. Atualiza o nível base de blocos
        if opens:
            level += 1
        elif closes and not starts_with_close:
            level = max(0, level - 1)

        # 4. Ativa o recuo estritamente para atribuições pendentes terminadas em '='
        # (ignora se a linha também já abriu um bloco com '{', '(', '[')
        if stripped.endswith("=") and not opens:
            pending_assign = True
        else:
            pending_assign = False

    with open(file, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


if __name__ == "__main__":
    fix_indent(Path(__file__).resolve().parents[2] / "src/pages/index/user-profile-flyout.js")
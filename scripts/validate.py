#!/usr/bin/env python3
"""Проверяет, что каждый скилл в skills/ оформлен правильно."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def parse_frontmatter(text):
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    fields = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def check_skill(skill_dir):
    errors = []
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return [f"{skill_dir.name}: нет файла SKILL.md"]
    fields = parse_frontmatter(skill_file.read_text(encoding="utf-8"))
    if fields is None:
        return [f"{skill_dir.name}: нет frontmatter между строками ---"]
    name = fields.get("name", "")
    description = fields.get("description", "")
    if name != skill_dir.name:
        errors.append(f"{skill_dir.name}: name «{name}» не совпадает с именем папки")
    if not NAME_RE.match(name) or len(name) > 64:
        errors.append(f"{skill_dir.name}: name должен быть в kebab-case латиницей, до 64 символов")
    if not description:
        errors.append(f"{skill_dir.name}: пустой description")
    elif len(description) > 1024:
        errors.append(f"{skill_dir.name}: description длиннее 1024 символов")
    elif "Используй" not in description:
        errors.append(f"{skill_dir.name}: в description нет фразы «Используй, когда…»")
    return errors


def main():
    skills = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir())
    errors = []
    for skill_dir in skills:
        errors.extend(check_skill(skill_dir))
    if errors:
        print("\n".join(errors))
        return 1
    print(f"OK: {len(skills)} скиллов прошли проверку")
    return 0


if __name__ == "__main__":
    sys.exit(main())

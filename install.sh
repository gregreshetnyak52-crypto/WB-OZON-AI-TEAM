#!/usr/bin/env sh
# Устанавливает скиллы WB-OZON-AI-TEAM в папку скиллов агента.
#   sh install.sh                 → ~/.claude/skills (Claude Code)
#   sh install.sh <путь>          → в любую другую папку скиллов
set -eu

SRC_DIR="$(cd "$(dirname "$0")" && pwd)/skills"
DEST_DIR="${1:-$HOME/.claude/skills}"

mkdir -p "$DEST_DIR"
for skill in "$SRC_DIR"/*/; do
  name="$(basename "$skill")"
  rm -rf "$DEST_DIR/$name"
  cp -R "$skill" "$DEST_DIR/$name"
  echo "  + $name"
done
echo "Готово: скиллы установлены в $DEST_DIR"

#!/usr/bin/env bash
set -euo pipefail

if ! command -v git >/dev/null 2>&1; then
  echo "git no esta instalado." >&2
  exit 1
fi

PYTHON_BIN=""
if command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "python no esta instalado." >&2
  exit 1
fi

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  echo "Uso: scripts/release.sh X.Y.Z" >&2
  exit 1
fi

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Formato de version invalido. Usa X.Y.Z" >&2
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Hay cambios sin commitear. Commitea o guarda antes de release." >&2
  exit 1
fi

TAG="v$VERSION"

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "El tag $TAG ya existe." >&2
  exit 1
fi

DATE="$(date +%Y-%m-%d)"

"$PYTHON_BIN" - "$VERSION" "$DATE" <<'PY'
import re
import sys
from pathlib import Path

version = sys.argv[1]
date = sys.argv[2]
path = Path("CHANGELOG.md")
text = path.read_text()

if f"## [{version}]" in text:
    print("La version ya existe en CHANGELOG.")
    sys.exit(1)

pattern = r"## \\[Unreleased\\]\\r?\\n"
if not re.search(pattern, text):
    print("No se encontro la seccion [Unreleased] en CHANGELOG.")
    sys.exit(1)

replacement = f"## [Unreleased]\\n\\n## [{version}] - {date}\\n"
text = re.sub(pattern, replacement, text, count=1)
path.write_text(text)
print("CHANGELOG actualizado.")
PY

git add CHANGELOG.md
git commit -m "Release $TAG"
git tag "$TAG"
echo "Release creada: $TAG"
echo "Recorda hacer: git push && git push --tags"

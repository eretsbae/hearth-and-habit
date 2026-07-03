#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# 이 폴더(hearth-and-habit/)를 독립된 새 GitHub 리포지토리로 옮기는 스크립트.
#
# 사전 준비:
#   1. https://github.com/new 에서 "hearth-and-habit" 이름의
#      "비어있는" Public 리포지토리를 만드세요 (README 추가하지 말 것).
#   2. 로컬에 git이 설치되어 있고 GitHub 인증이 되어 있어야 합니다.
#
# 사용법 (hearth-and-habit 폴더 안에서 실행):
#   bash scripts/migrate_to_new_repo.sh https://github.com/USERNAME/hearth-and-habit.git
# ─────────────────────────────────────────────────────────────
set -euo pipefail

REPO_URL="${1:?사용법: bash scripts/migrate_to_new_repo.sh <새 리포지토리 URL>}"

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"

echo "==> 프로젝트 복사: $SRC_DIR -> $TMP_DIR"
cp -r "$SRC_DIR/." "$TMP_DIR/"
rm -rf "$TMP_DIR/.git" "$TMP_DIR/_site" "$TMP_DIR/__pycache__"

cd "$TMP_DIR"
git init -b main
git add -A
git commit -m "Initial commit: Hearth & Habit automated blog"
git remote add origin "$REPO_URL"
git push -u origin main

echo ""
echo "✅ 완료! 다음 단계:"
echo "   1. 리포지토리 Settings → Pages → Source를 'GitHub Actions'로 설정"
echo "   2. Settings → Secrets and variables → Actions에 ANTHROPIC_API_KEY 등록"
echo "   3. Actions 탭에서 'Deploy Site' 워크플로우를 수동 실행(Run workflow)"
echo "   자세한 안내: docs/SETUP_GUIDE.md"

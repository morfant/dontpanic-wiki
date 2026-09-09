#!/bin/zsh
# DontPanic 볼트 Concepts의 빈 노트(스텁)를 claude 헤드리스로 채우는 스크립트.
# launchd가 매일 실행. 스텁이 없으면 claude를 띄우지 않고 종료.
# 수동: zsh scripts/fill-stubs.sh            (실제 실행)
#       zsh scripts/fill-stubs.sh --list     (스텁 목록만)
set -u

export PATH="/Users/giy/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/opt/homebrew/bin"
export HOME="/Users/giy"

VAULT="/Users/giy/Library/Mobile Documents/iCloud~md~obsidian/Documents/DontPanic"
REPO="/Users/giy/Projects/obsidian_wiki"
LOCKDIR="$REPO/.fill-stubs.lock"
MODE="${1:---auto}"

log() { echo "[$(date '+%F %T')] $*"; }

if ! mkdir "$LOCKDIR" 2>/dev/null; then
  log "another fill-stubs is running, exit"
  exit 0
fi
trap 'rmdir "$LOCKDIR"' EXIT

if [ ! -d "$VAULT/Concepts" ]; then
  log "ERROR: vault not accessible: $VAULT"
  exit 1
fi

brctl download "$VAULT/Concepts" 2>/dev/null || true
sleep 3

# 사전 검사: 300바이트 미만이고 ai-generated가 아닌 노트가 하나라도 있는가
n=0
for f in "$VAULT/Concepts"/**/*.md(N); do
  [ "$(wc -c <"$f")" -lt 300 ] || continue
  grep -q "ai-generated: true" "$f" && continue
  n=$((n+1))
done
if [ "$n" -eq 0 ]; then
  log "no stub candidates, skip"
  exit 0
fi
log "stub candidates: $n, running claude ($MODE)"

cd "$REPO" || exit 1
claude -p "/fill-stubs $MODE" \
  --permission-mode acceptEdits \
  --add-dir "$VAULT" \
  --allowedTools "Read" "Write" "Edit" "Glob" "Grep" "Agent" "WebSearch" "WebFetch" \
                 "Bash(find:*)" "Bash(ls:*)" "Bash(wc:*)" "Bash(grep:*)" "Bash(date:*)" "Bash(cat:*)" "Bash(head:*)" \
  --max-turns 120 < /dev/null \
  2>&1
rc=$?
log "claude exited: $rc"
exit $rc

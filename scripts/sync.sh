#!/bin/zsh
# DontPanic 볼트 -> obsidian_wiki content/ 동기화 스크립트
# launchd가 30분마다 실행. 변경이 있을 때만 commit/push -> GitHub Actions가 빌드/배포.
set -u

# launchd 환경에는 셸 프로필이 없으므로 PATH 명시
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/opt/homebrew/bin"

VAULT="/Users/giy/Library/Mobile Documents/iCloud~md~obsidian/Documents/DontPanic"
REPO="/Users/giy/Projects/obsidian_wiki"
# 공개할 볼트 폴더 목록 (공백 구분). 폴더를 추가 공개하려면 여기에 추가.
SYNC_FOLDERS=(Concepts)
IMG_SRC="$VAULT/Imgs"
LOCKDIR="$REPO/.sync.lock"

log() { echo "[$(date '+%F %T')] $*"; }

# 중복 실행 방지
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  log "another sync is running, exit"
  exit 0
fi
trap 'rmdir "$LOCKDIR"' EXIT

if [ ! -d "$VAULT" ]; then
  log "ERROR: vault not accessible: $VAULT (iCloud/TCC 권한 확인 필요)"
  exit 1
fi

# iCloud 파일 강제 다운로드 (플레이스홀더 방어)
brctl download "$VAULT" 2>/dev/null || true
sleep 3

# 1) 지정 폴더 rsync
for folder in "${SYNC_FOLDERS[@]}"; do
  src="$VAULT/$folder/"
  dst="$REPO/content/$folder/"
  [ -d "$src" ] || { log "WARN: $src 없음, skip"; continue; }
  mkdir -p "$dst"
  rsync -a --delete \
    --exclude='.DS_Store' \
    --exclude='.*.icloud' \
    --exclude='*.docx' \
    --exclude='*.pdf' \
    "$src" "$dst"
done

# 2) 노트가 참조하는 이미지만 선별 복사 (개인 사진 노출 방지)
IMG_DST="$REPO/content/Imgs"
mkdir -p "$IMG_DST"
refs="$(mktemp)"
# ![[파일명.png|349]] / ![[파일명.jpeg]] 형태에서 이미지 파일명 추출
find "$REPO/content" -name '*.md' -not -path "$IMG_DST/*" -exec cat {} + 2>/dev/null |
  grep -ohE '!\[\[[^]|]+\.(png|jpe?g|gif|webp|svg)' 2>/dev/null |
  sed 's/^!\[\[//' | sort -u > "$refs"

# 참조된 이미지를 볼트 Imgs에서 복사
while IFS= read -r name; do
  [ -n "$name" ] || continue
  src_img="$(find "$IMG_SRC" -name "$name" -print -quit 2>/dev/null)"
  if [ -n "$src_img" ]; then
    cp -p "$src_img" "$IMG_DST/" 2>/dev/null || true
  else
    log "WARN: 참조 이미지 없음: $name"
  fi
done < "$refs"

# 참조가 사라진 이미지는 content에서 제거
for f in "$IMG_DST"/*(N); do
  base="$(basename "$f")"
  if ! grep -qxF "$base" "$refs"; then
    rm -f "$f"
    log "removed unreferenced image: $base"
  fi
done
rm -f "$refs"

# 3) 변경 감지 후 commit/push
cd "$REPO" || exit 1
if [ -z "$(git status --porcelain -- content/)" ]; then
  log "no changes"
  exit 0
fi

git add content/
git commit -m "sync: $(date '+%F %T')" --quiet
if git push --quiet origin main 2>&1; then
  log "pushed: $(git log -1 --oneline)"
else
  log "ERROR: git push failed"
  exit 1
fi

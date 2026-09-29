#!/usr/bin/env python3
"""Zotero 파랑 하이라이트 중 영어 단어/정의를 볼트의 영단어장 노트에 추가한다.

- Zotero DB를 immutable 모드로 읽음 (Zotero 실행 중에도 안전)
- 한글 없는 영어 하이라이트만 대상, 뜻은 `claude -p`로 생성 (Zotero 코멘트가 있으면 우선)
- 처리한 annotation key는 볼트의 STATE 파일에 기록 → 노트에서 지운 항목은 다시 추가되지 않음
수동: python3 scripts/zotero-vocab.py [--dry-run]
"""
import json, re, sqlite3, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

COLOR = "#2ea8e5"  # Zotero 기본 팔레트의 파랑
DB = Path.home() / "Zotero/zotero.sqlite"
VAULT = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/DontPanic"
NOTE = VAULT / "영단어장.md"
STATE = VAULT / ".zotero-vocab-seen.json"
DRY = "--dry-run" in sys.argv

QUERY = """
select i.key, i.dateAdded, a.pageLabel, a.text, coalesce(a.comment, ''),
  (select v.value from itemAttachments att
     join itemData d on d.itemID = att.parentItemID
     join fields f on f.fieldID = d.fieldID and f.fieldName = 'title'
     join itemDataValues v on v.valueID = d.valueID
   where att.itemID = a.parentItemID)
from itemAnnotations a join items i on i.itemID = a.itemID
where a.color = ? and a.type in (1, 5)  -- 하이라이트, 밑줄
order by i.dateAdded
"""

HANGUL = re.compile(r"[가-힣]")


def log(msg):
    print(f"[{datetime.now():%F %T}] {msg}", flush=True)


def load_candidates(seen):
    con = sqlite3.connect(f"file:{DB}?immutable=1", uri=True)
    rows = con.execute(QUERY, (COLOR,)).fetchall()
    con.close()
    out = []
    for key, added, page, text, comment, title in rows:
        text = " ".join((text or "").split())
        if key in seen or not text or HANGUL.search(text):
            continue
        if len(re.findall(r"[A-Za-z]", text)) < 0.6 * len(text.replace(" ", "")):
            continue  # PDF 텍스트 레이어가 깨진 하이라이트
        local = datetime.strptime(added, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).astimezone()
        out.append(dict(key=key, date=f"{local:%Y-%m-%d}", page=page or "", text=text,
                        comment=comment.strip(), source=title or ""))
    return out


PROMPT = """아래 JSON은 영어 원서를 읽다 하이라이트한 단어·구절 목록이다. 각 항목을 영단어장 항목으로 만들어라.

규칙:
- term: 표제어. OCR 오타·잘린 글자·불필요한 문장부호를 고치고, 일반 단어는 소문자 기본형이 아닌 하이라이트된 형태 그대로 둔다(예: refracts). 긴 문장이 어떤 용어를 정의하는 문장이면 그 용어를 표제어로 뽑는다.
- def: 한국어 뜻. 출처(source) 문맥에 맞는 의미를 짧게(한 줄, 80자 이내). 인물·고유명사면 누구/무엇인지 한 줄. 정의 문장이면 그 정의를 한국어로 요약.
- comment가 있으면 사용자가 직접 단 뜻이므로 def의 앞부분에 그대로 살린다.
- 같은 표제어를 설명하는 항목이 여러 개면 첫 항목 하나에 뜻을 합치고 나머지는 skip.
- 의미 없는 문장 조각이거나 영단어장에 넣을 가치가 없으면 {"key": ..., "skip": true}.
- 출력은 JSON 배열만. 설명·코드펜스 없이. 각 원소: {"key": ..., "term": ..., "def": ...}

입력:
"""


def define(items):
    payload = [{k: it[k] for k in ("key", "text", "comment", "source")} for it in items]
    res = subprocess.run(["claude", "-p", PROMPT + json.dumps(payload, ensure_ascii=False)],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=600)
    if res.returncode != 0:
        raise RuntimeError(f"claude failed: {res.stderr.strip()[:500]}")
    body = res.stdout
    return {r["key"]: r for r in json.loads(body[body.index("["): body.rindex("]") + 1])}


def render(items, defs, note_text):
    lines = []
    if not re.search(r"^# 2026\s*$", note_text, re.M):
        lines += ["", "# 2026"]
    headers = re.findall(r"^\*\*(\d{4}-\d{2}-\d{2})\*\*\s*$", note_text, re.M)
    last = headers[-1] if headers else None
    for it in items:
        d = defs.get(it["key"])
        if not d or d.get("skip"):
            continue
        if it["date"] != last:
            lines += ["", f"**{it['date']}**"]
            last = it["date"]
        src = f"*{it['source']}*" if it["source"] else ""
        if it["page"]:
            page = it["page"] if it["page"].startswith("p.") else f"p. {it['page']}"
            src = f"{src}, {page}" if src else page
        lines.append(f"- **{d['term']}** : {d['def']}" + (f" ({src})" if src else ""))
    return lines


def main():
    seen = set(json.loads(STATE.read_text())) if STATE.exists() else set()
    items = load_candidates(seen)
    if not items:
        log("no new highlights")
        return
    log(f"new highlights: {len(items)}")
    defs = define(items)
    note_text = NOTE.read_text()
    lines = render(items, defs, note_text)
    if DRY:
        print("\n".join(lines))
        return
    if any(l.startswith("- ") for l in lines):
        NOTE.write_text(note_text.rstrip("\n") + "\n" + "\n".join(lines) + "\n")
    # claude가 응답하지 않은 key는 다음 실행에서 재시도
    STATE.write_text(json.dumps(sorted(seen | set(defs)), indent=0))
    log(f"added {sum(l.startswith('- ') for l in lines)}, skipped {sum(1 for d in defs.values() if d.get('skip'))}")


if __name__ == "__main__":
    main()

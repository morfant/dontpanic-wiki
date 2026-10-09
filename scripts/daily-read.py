#!/usr/bin/env python3
"""볼트 루트의 '오늘 읽기.md'를 만들고 미리 알림으로 아이폰에 알린다. 아이맥 launchd가 매일 아침 실행.

- 읽을거리: 볼트 수업노트/**/*_정리.md 의 '## ' 섹션 하나하나 (찾아볼 것·공지·연결 고리 제외)
- 하루 분량: 새 섹션 1개 + 복습할 때가 된 섹션 1개(있으면)
- 읽음 처리: '오늘 읽기.md'의 '- [ ] 읽음' 을 체크하면 다음 실행 때 반영.
  체크한 섹션은 1·3·7·21·60일 뒤에 다시 나오고, 체크 안 한 섹션은 다음 날 그대로 다시 나온다.
- 알림: 기본 목록에 '오늘 읽기 MM/DD 📖' 미리 알림을 1분 뒤 알람으로 만들고, 안 끝난 이전 것은 완료 처리.
  iCloud로 아이폰에 동기화돼 잠금 화면 알림이 뜬다.
- 내게 보내는 iMessage는 아이폰에 알림이 안 떠서 기록용. STATE_DIR/imessage-handle 파일이 있을 때만 보낸다.
- 상태와 수신 주소는 레포 밖(STATE_DIR)에 둔다. 레포가 공개이므로.
- iCloud 파일명은 기기에 따라 NFD로 올 수 있어 경로·id를 NFC로 맞춘다.

  --dry-run  노트를 쓰지 않고 오늘 고를 내용만 출력 (상태도 안 바꿈)
  --no-send  노트는 쓰되 알림은 보내지 않음
  --resend   오늘 이미 실행했으면 같은 내용으로 알림만 다시 보냄
"""
import datetime, json, pathlib, re, subprocess, sys, unicodedata, urllib.parse

VAULT = pathlib.Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/DontPanic"
NOTES = VAULT / "수업노트"
OUT = VAULT / "오늘 읽기.md"
STATE_DIR = pathlib.Path.home() / "Library/Application Support/obsidian-daily-read"
STATE = STATE_DIR / "state.json"
HANDLE = STATE_DIR / "imessage-handle"
INTERVALS = [1, 3, 7, 21, 60]  # 읽음 체크 n번째 이후 다음 복습까지 일수
SKIP_HEADINGS = ("찾아볼 것", "공지", "오늘 수업의 연결 고리", "0. 발제 안내", "0. 읽기 안내", "2. 과제와 평가", "3. 읽기 목록")
CHECK_RE = re.compile(r"^- \[( |x|X)\] 읽음 <!-- id:(.+?) -->$", re.M)
DATE_RE = re.compile(r"(\d{6})_정리$")


def sections():
    """(id, 노트 stem, 제목, 본문) 목록. 최근 수업이 먼저, 노트 안에서는 위에서부터."""
    nfc = lambda x: unicodedata.normalize("NFC", x)
    notes = [p for p in NOTES.rglob("*.md") if DATE_RE.search(nfc(p.stem))]
    notes.sort(key=lambda p: DATE_RE.search(nfc(p.stem)).group(1), reverse=True)
    out = []
    for p in notes:
        stem = nfc(p.stem)
        text = p.read_text(encoding="utf-8")
        parts = re.split(r"^## (.+)$", text, flags=re.M)
        for heading, body in zip(parts[1::2], parts[2::2]):
            heading = nfc(heading.strip())
            if heading.startswith(SKIP_HEADINGS):
                continue
            body = re.sub(r"\n-{3,}\s*$", "", body.strip()).strip()
            if body:
                out.append((f"{stem}#{heading}", stem, heading, body))
    return out


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"items": {}, "shown": []}


def apply_checks(state, today):
    """어제 노트의 체크 상태를 반영. 체크 안 된 id 목록을 돌려준다."""
    if not OUT.exists():
        return []
    unread = []
    for mark, sid in CHECK_RE.findall(OUT.read_text(encoding="utf-8")):
        if sid not in state["shown"]:
            continue
        if mark.strip():
            it = state["items"].setdefault(sid, {"stage": 0})
            gap = INTERVALS[min(it["stage"], len(INTERVALS) - 1)]
            it["stage"] += 1
            it["last"] = today.isoformat()
            it["due"] = (today + datetime.timedelta(days=gap)).isoformat()
        else:
            unread.append(sid)
    return unread


def pick(secs, state, unread, today):
    by_id = {s[0]: s for s in secs}
    chosen = [by_id[i] for i in unread if i in by_id]  # 어제 못 읽은 것은 그대로 다시
    if all(s[0] in state["items"] for s in chosen):
        new = next((s for s in secs if s[0] not in state["items"]), None)
        if new:
            chosen.append(new)
    if not any(s[0] in state["items"] for s in chosen):
        due = sorted((it["due"], sid) for sid, it in state["items"].items()
                     if sid in by_id and it.get("due", "9999") <= today.isoformat())
        if due:
            chosen.append(by_id[due[0][1]])
    return chosen


def render(chosen, state, today):
    lines = [f"# 오늘 읽기 · {today.isoformat()}", ""]
    if not chosen:
        lines += ["오늘은 읽을 섹션이 없습니다. 새 수업 정리가 생기면 다시 나타나요."]
    for sid, stem, heading, body in chosen:
        it = state["items"].get(sid)
        tag = "새로 읽기" if it is None else f"복습 {it['stage']}회차"
        lines += ["---", "", f"## {heading}",
                  f"*{tag} · [[{stem}#{heading}|{stem}]]*", "",
                  body, "", f"- [ ] 읽음 <!-- id:{sid} -->", ""]
    return "\n".join(lines).rstrip() + "\n"


REMIND_SCRIPT = '''on run argv
tell application "Reminders" to launch
delay 5  -- 꺼져 있던 앱이 뜨는 중이면 -600(앱이 실행 중이 아님)이 난다
tell application "Reminders"
  set L to default list
  repeat with r in (reminders of L whose completed is false and name starts with "오늘 읽기 ")
    set completed of r to true
  end repeat
  set d to (current date) + 60
  make new reminder at end of L with properties {name:(item 1 of argv), body:(item 2 of argv), due date:d, remind me date:d}
end tell
end run'''


def send(chosen, today):
    if not chosen:
        return
    url = "obsidian://open?" + urllib.parse.urlencode(
        {"vault": VAULT.name, "file": OUT.stem}, quote_via=urllib.parse.quote)
    titles = "\n".join(f"· {h} ({stem.replace('_정리', '')})" for _, stem, h, _ in chosen)
    title = f"오늘 읽기 {today.strftime('%m/%d')} 📖"
    subprocess.run(["osascript", "-e", REMIND_SCRIPT, title, f"{titles}\n{url}"], check=True, timeout=120)
    if not HANDLE.exists():
        return
    handle = HANDLE.read_text(encoding="utf-8").strip()
    msg = f"📖 오늘 읽기 {today.strftime('%m/%d')}\n{titles}\n{url}"
    script = '''on run argv
tell application "Messages"
  set svc to 1st account whose service type = iMessage
  send (item 2 of argv) to participant (item 1 of argv) of svc
end tell
end run'''
    subprocess.run(["osascript", "-e", script, handle, msg], check=True, timeout=60)


def main():
    dry = "--dry-run" in sys.argv
    today = datetime.date.today()
    subprocess.run(["brctl", "download", str(VAULT)], capture_output=True)
    state = load_state()
    if state.get("date") == today.isoformat() and not dry:
        if "--resend" in sys.argv:  # 오늘 고른 것으로 알림만 다시
            by_id = {s[0]: s for s in sections()}
            send([by_id[i] for i in state["shown"] if i in by_id], today)
            print("resent")
        else:
            print("already ran today")
        return
    unread = apply_checks(state, today)
    secs = sections()
    chosen = pick(secs, state, unread, today)
    if dry:
        for sid, *_ in chosen:
            print(sid)
        return
    OUT.write_text(render(chosen, state, today), encoding="utf-8")
    state["shown"] = [s[0] for s in chosen]
    state["date"] = today.isoformat()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    if "--no-send" not in sys.argv:
        send(chosen, today)
    print(f"{today}: {len(chosen)} section(s), {len(secs)} total")


if __name__ == "__main__":
    main()

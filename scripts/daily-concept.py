#!/usr/bin/env python3
"""content/index.md의 '오늘의 개념' 블록을 갱신한다. sync.sh가 rsync 뒤에 호출.

- 후보: content/Concepts/*.md 중 draft: true 아님, isRead: true 아님, 본문 200자 이상
- 선택: 날짜+파일명의 md5가 가장 작은 것 (rendezvous hashing). 같은 날에는 같은 노트,
  다른 노트를 읽음 처리해도 오늘의 선택은 바뀌지 않음.
- 출력: index.md의 <!-- daily-concept:start --> ~ <!-- daily-concept:end --> 사이만 교체.
"""
import datetime, hashlib, pathlib, re, sys

REPO = pathlib.Path(__file__).resolve().parent.parent
CONCEPTS = REPO / "content" / "Concepts"
INDEX = REPO / "content" / "index.md"
START, END = "<!-- daily-concept:start -->", "<!-- daily-concept:end -->"
FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def split(text):
    m = FM_RE.match(text)
    return (m.group(1), text[m.end():]) if m else ("", text)


def fm_flag(fm, key):
    m = re.search(rf"^{key}:\s*(\S+)", fm, re.M)
    return m.group(1).lower() == "true" if m else False


def candidates():
    out = []
    for p in sorted(CONCEPTS.glob("*.md")):
        fm, body = split(p.read_text(encoding="utf-8"))
        if fm_flag(fm, "draft") or fm_flag(fm, "isRead"):
            continue
        if len(body.strip()) < 200:
            continue
        out.append((p, body))
    return out


def excerpt(body, limit=160):
    for para in re.split(r"\n\s*\n", body):
        para = " ".join(l.strip() for l in para.splitlines() if l.strip())
        if not para or para.startswith(("#", "-", "*", "!", ">", "|")):
            continue
        para = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", para)
        para = re.sub(r"\[\[([^\]]+)\]\]", r"\1", para)
        para = para.replace("**", "")
        if len(para) < 40:
            continue
        return para if len(para) <= limit else para[:limit].rstrip() + "…"
    # 단락이 없는 목록형 노트: 첫 목록 항목들을 이어 붙인다
    items = [re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", l) for l in body.splitlines()
             if re.match(r"^\s*(?:[-*]|\d+\.)\s+\S", l) and not l.lstrip().startswith("- [[")]
    joined = " · ".join(items[:4])
    joined = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", joined)
    joined = re.sub(r"\[\[([^\]]+)\]\]", r"\1", joined).replace("**", "")
    return joined if len(joined) <= limit else joined[:limit].rstrip() + "…"


def main():
    today = datetime.date.today().isoformat()
    cands = candidates()
    if not cands:
        block = f"{START}\n{END}"
    else:
        pick, body = min(cands, key=lambda c: hashlib.md5(f"{today}\n{c[0].name}".encode()).hexdigest())
        name = pick.stem
        lines = [START, f"## 오늘의 개념 · {today}", "", f"### [[Concepts/{name}|{name}]]"]
        ex = excerpt(body)
        if ex:
            lines += ["", f"> {ex}"]
        lines += ["", f"아직 읽지 않은 개념 {len(cands)}개가 남아 있습니다. 읽었으면 옵시디언에서 `isRead`를 켜 주세요.", END]
        block = "\n".join(lines)

    text = INDEX.read_text(encoding="utf-8")
    if START in text and END in text:
        new = text[: text.index(START)] + block + text[text.index(END) + len(END):]
    else:
        # 마커가 없으면 인트로 단락 뒤(첫 목록 앞)에 삽입
        idx = text.find("\n- ")
        idx = len(text) if idx < 0 else idx + 1
        new = text[:idx] + block + "\n\n" + text[idx:]
    if new != text:
        INDEX.write_text(new, encoding="utf-8")
        print(f"daily-concept: {pick.stem if cands else '(none)'} ({len(cands)} unread)")


if __name__ == "__main__":
    sys.exit(main())

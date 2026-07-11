# DontPanic Wiki

Obsidian 볼트 `DontPanic`의 **Concepts 폴더**를 Quartz 5 기반 위키로 자동 퍼블리싱하는 프로젝트.

- 사이트: https://morfant.github.io/dontpanic-wiki (GitHub Pages, repo: morfant/dontpanic-wiki)
- 볼트 경로: `/Users/giy/Library/Mobile Documents/iCloud~md~obsidian/Documents/DontPanic`
- 구축: 2026-07-11

## 아키텍처

```
[iCloud 볼트] → launchd(30분 주기) → scripts/sync.sh
  → content/ 에 rsync + 참조 이미지 선별 복사 → 변경 시 git commit/push
  → GitHub Actions(deploy.yml) → npx quartz plugin install && npx quartz build → Pages 배포
```

- Quartz 코어: upstream/v5 브랜치 추적 (`upstream` 리모트 = jackyzha0/quartz). 커스터마이즈는 `quartz.config.yaml`만.
- `content/`는 sync.sh가 관리 (index.md 제외 — 직접 편집). 볼트 원본을 편집하고 content/는 건드리지 말 것.

## 주요 명령

- 즉시 동기화: `launchctl kickstart gui/$UID/com.giy.obsidian-wiki-sync` (로그: `~/Library/Logs/obsidian-wiki-sync.log`)
- 로컬 프리뷰: `nvm use 22 && npx quartz build --serve` (Node 22 필수, `.nvmrc` 참조. **nvm default(18)는 바꾸지 말 것** — claude CLI가 node18 global에 설치됨)
- 빈 노트 채우기: `/fill-stubs` skill (`.claude/skills/fill-stubs/`) — 웹 조사로 볼트 원본에 직접 작성, `ai-generated: true` 표시
- 공개 폴더 추가: `scripts/sync.sh` 상단 `SYNC_FOLDERS` 배열에 폴더명 추가
- 노트 단위 비공개: 프론트매터에 `draft: true`

## 주의사항 (겪은 문제들)

- **플러그인·코어 버전 짝**: 커뮤니티 플러그인(explorer/graph/search)은 코어의 `<body data-basepath>`와 `fetchData`에 의존. 플러그인만 업데이트하면 서브패스 호스팅에서 링크가 깨짐 → 코어(upstream/v5)와 플러그인을 함께 업데이트하고 `quartz.lock.json` 커밋.
- CLI: `npx quartz plugin install` (구 `plugin restore`는 제거됨). deploy.yml도 동일 명령 사용.
- URL 슬러그는 전부 소문자 (`/concepts/...`).
- launchd가 iCloud에 접근하려면 `/bin/zsh`에 전체 디스크 접근 권한 필요 (부여 완료. 재설치 시 재부여).
- 한국어 파일명: `core.precomposeunicode=true`, `core.quotepath=false` 설정됨.
- Sources 폴더의 PDF/docx는 저작권상 sync에서 제외.

## 검증 방법

- 배포 확인: `gh run list --repo morfant/dontpanic-wiki` 또는 actions/runs API
- 서브패스 회귀 진단: 라이브 HTML `<body>`에 `data-basepath="/dontpanic-wiki"` 존재, JS 번들에 `fetch("/static/contentIndex.json")` 절대경로 0건
- E2E: 볼트 Concepts에 테스트 노트 작성 → kickstart → 사이트 반영 / `draft: true` 노트는 404여야 함

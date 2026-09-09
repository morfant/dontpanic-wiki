# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

- **Quartz 코어**: upstream/v5 브랜치 추적 (`upstream` 리모트 = jackyzha0/quartz). `quartz/` 코드는 수정하지 않고, 커스터마이즈는 `quartz.config.yaml`만. `quartz.config.default.yaml`은 upstream 원본이므로 `diff` 하면 우리 변경점이 보임.
- **플러그인**: `quartz.config.yaml`의 `plugins:` 목록을 `npx quartz plugin install`이 `quartz.lock.json`(커밋 대상)에 고정된 커밋으로 `.quartz/plugins/`(gitignore)에 설치. 코어와 플러그인 모두 upstream 기본값 대신 우리 config를 따르므로 `quartz.config.yaml`이 사실상 유일한 설정 지점.
- **content/**는 `scripts/sync.sh`가 관리 (`content/index.md`만 직접 편집). 볼트 원본을 편집하고 content/는 건드리지 말 것. sync는 `content/`만 `git add` 하므로 index.md 수정도 다음 sync 커밋에 함께 실린다.
- **sync.sh 동작 요약**: `.sync.lock` 디렉토리로 중복 실행 방지 → `brctl download`로 iCloud 플레이스홀더 강제 다운로드 → `SYNC_FOLDERS` rsync(`--delete`, `.icloud`/pdf/docx 제외) → 노트가 `![[...]]`로 참조하는 이미지만 볼트 `Imgs/`에서 `content/Imgs/`로 복사하고 참조 끊긴 이미지는 삭제(개인 사진 노출 방지) → `content/` 변경 시에만 commit/push.
- `.github/workflows/` 중 실제 배포는 `deploy.yml`(push to main + workflow_dispatch). 나머지(ci.yaml, deploy-v5.yaml 등)는 upstream 잔재.

## 주요 명령

- 즉시 동기화: `launchctl kickstart gui/$UID/com.giy.obsidian-wiki-sync` (로그: `~/Library/Logs/obsidian-wiki-sync.log`). 수동 실행은 `zsh scripts/sync.sh`. plist 원본은 `scripts/*.plist` (설치: `~/Library/LaunchAgents/`에 복사 후 `launchctl bootstrap gui/$UID <plist>`)
- 로컬 프리뷰: `nvm use 22 && npx quartz plugin install && npx quartz build --serve` (Node 22 필수, `.nvmrc` 참조. **nvm default(18)는 바꾸지 말 것** — claude CLI가 node18 global에 설치됨)
- 코어 업데이트: `git fetch upstream && git merge upstream/v5` → `npx quartz plugin install` → 빌드 확인 → `quartz.lock.json` 커밋
- 코어 타입/포맷 검사(코어를 건드렸을 때만): `npm run check`, 테스트 `npm test`
- 빈 노트 채우기: `/fill-stubs` skill (`.claude/skills/fill-stubs/`) — 웹 조사로 볼트 원본에 직접 작성(`ai-generated: true`), 밀접한 기존 노트의 `## 연결` 섹션에 역방향 링크 추가(`<!-- ai-linked 날짜 -->` 주석). 인자: `--auto`(헤드리스), `--list`(목록만), `--no-backlink`
- 스텁 자동 채우기: launchd `com.giy.obsidian-wiki-fill-stubs`가 매일 04:30에 `scripts/fill-stubs.sh` 실행 → 스텁이 있으면 `claude -p "/fill-stubs --auto"`(acceptEdits, `--add-dir` 볼트) 로 최대 5개 처리. 로그: `~/Library/Logs/obsidian-wiki-fill-stubs.log`. 즉시 실행: `launchctl kickstart gui/$UID/com.giy.obsidian-wiki-fill-stubs`, 목록만: `zsh scripts/fill-stubs.sh --list`
- 공개 폴더 추가: `scripts/sync.sh` 상단 `SYNC_FOLDERS` 배열에 폴더명 추가
- 노트 단위 비공개: 프론트매터에 `draft: true` (remove-draft 플러그인)

## 주의사항 (겪은 문제들)

- **플러그인·코어 버전 짝**: 커뮤니티 플러그인(explorer/graph/search)은 코어의 `<body data-basepath>`와 `fetchData`에 의존. 플러그인만 업데이트하면 서브패스 호스팅에서 링크가 깨짐 → 코어(upstream/v5)와 플러그인을 함께 업데이트하고 `quartz.lock.json` 커밋.
- CLI: `npx quartz plugin install` (구 `plugin restore`는 제거됨). deploy.yml도 동일 명령 사용.
- URL 슬러그는 전부 소문자 (`/concepts/...`).
- launchd가 iCloud에 접근하려면 `/bin/zsh`에 전체 디스크 접근 권한 필요 (부여 완료. 재설치 시 재부여). launchd 환경에는 셸 프로필이 없어 sync.sh가 PATH를 직접 지정함.
- 한국어 파일명: `core.precomposeunicode=true`, `core.quotepath=false` 설정됨.
- Sources 폴더의 PDF/docx는 저작권상 sync에서 제외 (`quartz.config.yaml` ignorePatterns에도 이중 차단).

## 검증 방법

- 배포 확인: `gh run list --repo morfant/dontpanic-wiki` 또는 actions/runs API
- 서브패스 회귀 진단: 라이브 HTML `<body>`에 `data-basepath="/dontpanic-wiki"` 존재, JS 번들에 `fetch("/static/contentIndex.json")` 절대경로 0건
- E2E: 볼트 Concepts에 테스트 노트 작성 → kickstart → 사이트 반영 / `draft: true` 노트는 404여야 함

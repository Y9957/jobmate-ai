# JobMate AI

> **LLM이 제시한 근거가 실제로 맞는지 검증하고, 그 정확도를 측정하는** 채용공고 적합성 분석 Agent

AI가 "적합도 85점"이라고만 말하는 대신, 공고의 요구조건마다 **이력서의 어떤 문장이 근거인지 인용**하고,
그 인용이 원문에 실제로 있는지 **코드로 대조**한 뒤 의미가 맞는지 다시 확인합니다.
그리고 이 검증이 근거 없는 매칭을 얼마나 줄이는지 **평가 데이터로 측정**하는 것이 이 프로젝트의 목표입니다.

설계 문서: [docs/design.md](docs/design.md)

## 진행 상황

| 단계 | 내용 | 상태 |
|---|---|---|
| 01 기반 | FastAPI, PostgreSQL, Docker Compose, Alembic 마이그레이션, 테스트, CI | ✅ |
| 02 분석 파이프라인 | LangGraph: Parser → Matcher → Span Check(코드) → Semantic Check(LLM) → Report | ⏳ |
| 03 평가 | 평가 데이터 20~30건, 라벨 기준표, 단일 프롬프트 베이스라인과 비교 | |
| 04 API | 이력서·공고·분석·지원현황, 근거 수정 → 재검증 | |
| 05 화면 | React + TypeScript + Vite | |
| 06 배포 | 샘플 전용 데모, 시연 영상 | |

## 실행

Docker만 있으면 됩니다.

```bash
docker compose up -d --build
curl http://localhost:8000/health
# {"status":"ok","database":"ok","version":"0.1.0"}
```

API 문서: http://localhost:8000/docs

컨테이너가 시작될 때 `alembic upgrade head`로 스키마가 자동 적용됩니다.

### 테스트 (로컬)

테스트는 실제 PostgreSQL에서 돌고, 개발 데이터와 분리된 `jobmate_test` DB를 자동으로 만듭니다.

```bash
docker compose up -d db
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q
```

## 구조

```
backend/
  app/
    main.py        FastAPI 앱
    config.py      환경 변수 설정 (DATABASE_URL 등)
    db.py          SQLAlchemy 엔진·세션
    models.py      resumes · job_postings · analyses · match_evidence · applications
    api/health.py  /health — DB 왕복 확인, 실패 시 503
  migrations/      Alembic 마이그레이션
  tests/           헬스체크, 스키마·마이그레이션 일치, 제약조건, cascade
docker-compose.yml PostgreSQL 16 + API
docs/design.md     설계 문서
```

## 데이터·개인정보 원칙

- 이력서 **원본 PDF는 저장하지 않고**, 개인정보를 가린 텍스트(`masked_text`)만 저장합니다.
- 공개 데모는 **샘플 이력서 전용**으로 운영합니다.
- 평가 데이터는 가상 이력서와 재작성한 공고만 사용합니다.

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 · Docker Compose · pytest · Ruff · GitHub Actions
(예정: LangGraph · Pydantic · PyMuPDF · React · TypeScript)

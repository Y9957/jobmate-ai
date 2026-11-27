# JobMate AI

> **LLM이 제시한 근거가 실제로 맞는지 검증하고, 그 정확도를 측정하는** 채용공고 적합성 분석 Agent

AI가 "적합도 85점"이라고만 말하는 대신, 공고의 요구조건마다 **이력서의 어떤 문장이 근거인지 인용**하고,
그 인용이 원문에 실제로 있는지 **코드로 대조**한 뒤 의미가 맞는지 다시 확인합니다.
그리고 이 검증이 근거 없는 매칭을 얼마나 줄이는지 **평가 데이터로 측정**하는 것이 이 프로젝트의 목표입니다.

설계 문서: [docs/design.md](docs/design.md) · 파이프라인 설계: [docs/agent-design.md](docs/agent-design.md)

## 진행 상황

| 단계 | 내용 | 상태 |
|---|---|---|
| 01 기반 | FastAPI, PostgreSQL, Docker Compose, Alembic 마이그레이션, 테스트, CI | ✅ |
| 02 분석 파이프라인 | LangGraph: Parser → Matcher → Span Check(코드) → Semantic Check(LLM) → Report | ✅ |
| 03 평가 | 25케이스·174개 요구조건(easy/dev/test 분리), 라벨 기준표, 검증 단계별 비교 | ✅ (로컬 모델) |
| 04 API | 이력서·공고·분석·지원현황, 근거 수정 → 재검증 | ⏳ |
| 05 화면 | React + TypeScript + Vite | |
| 06 배포 | 샘플 전용 데모, 시연 영상 | |

## 평가 결과 요약

로컬 `qwen3:8b`, 보지 않은 test 5케이스·40개 요구조건, 프롬프트 v5 · 상세: [evals/README.md](evals/README.md)

| 시스템 | 근거 없는 충족 판정 | 지어낸 인용 | 오탐 | 충족 재현율 | LLM 호출 |
|---|---:|---:|---:|---:|---:|
| A. 검증 없음 | 4.3% | 0.0% | 0.0% | 95.7% | 5 |
| C. 원문 대조 + 의미 검증 | 4.3% | 0.0% | 0.0% | 95.7% | 10 |

**보지 않은 test에서는 검증 단계가 차이를 만들지 못했습니다.** 다듬은 프롬프트의 8B 모델이 검증으로 잡을 오류를 거의 내지 않았기 때문입니다.
모델이 실제로 틀린 dev에서는 검증이 근거 없는 충족 판정을 10.3% → 0%, 지어낸 인용을 5.1% → 0%로 모두 걸러냈습니다(조정에 쓴 데이터라 낙관적).

평가 과정에서 검증 단계가 오히려 맞는 답을 버리게 만든 결함(재시도 피드백이 포기를 유도)을 찾아 고쳤고,
한 번 본 test는 dev로 옮긴 뒤 새 test를 만들어 다시 측정했습니다. 이 기록은 [evals/README.md](evals/README.md)에 그대로 남겨 두었습니다.

## 실행

Docker만 있으면 됩니다.

```bash
docker compose up -d --build
curl http://localhost:8000/health
# {"status":"ok","database":"ok","version":"0.1.0"}
```

API 문서: http://localhost:8000/docs

컨테이너가 시작될 때 `alembic upgrade head`로 스키마가 자동 적용됩니다.

### 분석 파이프라인 실행 (로컬 LLM)

[Ollama](https://ollama.com)로 로컬 모델을 띄운 뒤, 가상 이력서와 가상 공고로 분석을 돌려 볼 수 있습니다.

```bash
ollama pull qwen3:8b
cd backend
python -m app.cli samples/resume_sample.txt samples/job_sample.txt
```

```
필수 2/2  우대 2/3  제한 조건 1/1

[1] (필수) Python 기반 웹 백엔드 개발 경험 → 충족  [원문대조 O · 의미검증 O]
    근거: "FastAPI로 사내 분석 API 3종을 개발하고 Docker로 배포했습니다."
[5] (우대) Kubernetes 환경 운영 경험 → 미충족  [원문대조 - · 의미검증 -]
    설명: 이력서에 Kubernetes 환경 운영 경험에 대한 언급이 없습니다.
...
```

RTX 3060 12GB 기준 분석 1건(요구조건 6개)에 약 20초가 걸립니다.

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
    llm/           LLM 클라이언트 인터페이스 — Ollama(로컬), Fake(테스트)
    pipeline/      LangGraph 분석 파이프라인 — 마스킹, 공고 파싱, 매칭, 원문 대조, 의미 검증, 리포트
    cli.py         파이프라인 실행 도구
  migrations/      Alembic 마이그레이션
  samples/         가상 이력서·가상 공고
  tests/           헬스체크, 스키마, 원문 대조·마스킹, 파이프라인(재시도·강등·의미 검증)
docker-compose.yml PostgreSQL 16 + API
docs/design.md     설계 문서
```

## 데이터·개인정보 원칙

- 이력서 **원본 PDF는 저장하지 않고**, 개인정보를 가린 텍스트(`masked_text`)만 저장합니다.
- 공개 데모는 **샘플 이력서 전용**으로 운영합니다.
- 평가 데이터는 가상 이력서와 재작성한 공고만 사용합니다.

## Stack

Python 3.12 · FastAPI · LangGraph · Pydantic · SQLAlchemy 2 · Alembic · PostgreSQL 16 · Ollama · Docker Compose · pytest · Ruff · GitHub Actions
(예정: Claude API · PyMuPDF · React · TypeScript)

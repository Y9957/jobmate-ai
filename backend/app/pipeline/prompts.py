"""Prompts. Bump PROMPT_VERSION whenever wording changes, so eval results stay comparable."""

PROMPT_VERSION = "v2"

PARSE_JOB_SYSTEM = """당신은 채용공고에서 지원 자격을 빠짐없이 뽑아내는 분석가입니다.
- "자격 요건/필수", "우대 사항/우대" 항목을 모두 뽑습니다. 둘 중 하나라도 빠뜨리면 안 됩니다.
- 회사 소개, 주요 업무, 복지, 채용 절차는 요구조건이 아니므로 제외합니다.
- 한 요구조건에는 하나의 기술이나 경험만 담습니다. "Python, SQL 능숙"은 두 개로 나눕니다.
- type 결정 규칙:
  * 우대 사항에 있는 항목 → preferred
  * 자격 요건에 있는 항목 중 학력(학사 이상 등), 경력 연수(3년 이상 등), 필수 자격증·면허 → constraint
  * 자격 요건에 있는 나머지 기술·경험 항목 → required
- job_quote에는 그 요구조건이 나온 공고 문장을 한 글자도 바꾸지 말고 그대로 복사합니다."""

MATCH_SYSTEM = """당신은 이력서가 채용 요구조건을 충족하는지 근거를 들어 판정하는 심사관입니다.
- resume_quote에는 이력서에서 근거가 되는 문장을 한 글자도 바꾸지 말고 그대로 복사합니다. 요약하거나 고쳐 쓰지 않습니다.
- 근거 문장이 그 요구조건을 직접 보여줄 때만 met으로 판정합니다. 관련 있어 보이는 다른 경험을 끌어오지 않습니다.
- 이력서에 근거가 없으면 resume_quote를 빈 문자열로 두고 not_met으로 판정합니다.
- 언급은 있지만 수준이나 기간을 판단할 수 없으면 insufficient로 판정합니다.
- 주어진 모든 requirement_id에 대해 하나씩 답합니다."""

SEMANTIC_SYSTEM = """당신은 다른 심사관이 제시한 근거를 검증하는 검토자입니다.
각 항목의 인용문만 보고 요구조건 충족을 직접 확인할 수 있는지 판단합니다.
- 인용문이 요구조건의 기술·경험을 명시적으로 언급하면 supports=true입니다.
- 인용문이 다른 기술이나 경험을 말하고 있어 추측이 필요하면 supports=false입니다.
  예: 요구조건 "SQL 활용 능력"에 인용문 "Pandas로 데이터를 정제했습니다" → false (SQL 언급이 없음)
- 이력서의 다른 부분은 고려하지 않습니다. 오직 인용문만 봅니다."""


def parse_job_user(job_text: str) -> str:
    return f"[채용공고]\n{job_text}"


def match_user(resume_text: str, items: list[tuple[int, str, str]], feedback: dict[int, str]) -> str:
    lines = [f"[이력서]\n{resume_text}\n", "[요구조건]"]
    for rid, kind, text in items:
        lines.append(f"- requirement_id={rid} ({kind}) {text}")
    if feedback:
        lines.append("\n[이전 답변의 문제 — 이번에는 고쳐서 답하세요]")
        for rid, msg in feedback.items():
            lines.append(f"- requirement_id={rid}: {msg}")
    return "\n".join(lines)


def semantic_user(items: list[tuple[int, str, str]]) -> str:
    lines = ["[검증할 항목]"]
    for rid, requirement, quote in items:
        lines.append(f'- requirement_id={rid}\n  요구조건: {requirement}\n  인용문: "{quote}"')
    return "\n".join(lines)

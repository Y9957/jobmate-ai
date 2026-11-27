"""Prompts. Bump PROMPT_VERSION whenever wording changes, so eval results stay comparable."""

PROMPT_VERSION = "v5"

# Rules shared by the matcher and the semantic reviewer, so both stages apply the same policy
# (v4 had the skills-list rule only in the reviewer, and the matcher rejected skills-list evidence).
_SHARED_RULES = """- [기술] 섹션의 기술 목록에 있는 기술은 그 기술(또는 그 기술이 속한 도구·플랫폼 분류)의 "사용 경험·능력" 근거로 인정합니다.
  예: 기술 목록의 "Zabbix" → "모니터링 도구 사용 경험"의 근거. 단, 기간·규모·수준 요구는 기술 목록만으로 인정하지 않습니다.
- [관심 기술], [학습 중] 목록과 교육 수료는 사용 경험의 근거가 아닙니다.
- 경력 연수는 요구조건과 같은 직무의 경력 기간만 셉니다.
  예: "개발 실무 경력 2년 이상"에 "서비스 기획자 3년"은 근거가 아닙니다."""

PARSE_JOB_SYSTEM = """당신은 채용공고에서 지원 자격을 빠짐없이 뽑아내는 분석가입니다.
- "자격 요건/필수", "우대 사항/우대" 항목을 모두 뽑습니다. 둘 중 하나라도 빠뜨리면 안 됩니다.
- 회사 소개, 주요 업무, 복지, 채용 절차는 요구조건이 아니므로 제외합니다.
- 한 요구조건에는 하나의 기술이나 경험만 담습니다. "Python, SQL 능숙"은 두 개로 나눕니다.
- type 결정 규칙:
  * 우대 사항에 있는 항목 → preferred
  * 자격 요건에 있는 항목 중 학력(학사 이상 등), 경력 연수(3년 이상 등), 필수 자격증·면허 → constraint
  * 자격 요건에 있는 나머지 기술·경험 항목 → required
- job_quote에는 그 요구조건이 나온 공고 문장을 한 글자도 바꾸지 말고 그대로 복사합니다."""

MATCH_SYSTEM = (
    """당신은 이력서가 채용 요구조건을 충족하는지 근거를 들어 판정하는 심사관입니다.
- resume_quote에는 이력서에서 근거가 되는 문장을 한 글자도 바꾸지 말고 그대로 복사합니다. 요약하거나 고쳐 쓰지 않습니다.
- 인용은 이력서의 한 줄 안에서만 합니다. 섹션 제목, 회사·프로젝트 이름, 날짜를 앞에 붙이지 않습니다.
  예: "- Spark로 로그를 정제했습니다." 줄이 근거라면 resume_quote는 "Spark로 로그를 정제했습니다."
- 근거 문장이 그 요구조건을 직접 보여줄 때만 met으로 판정합니다. 관련 있어 보이는 다른 경험을 끌어오지 않습니다.
- 이력서에 근거가 없으면 resume_quote를 빈 문자열로 두고 not_met으로 판정합니다.
- 언급은 있지만 수준이나 기간을 판단할 수 없으면 insufficient로 판정합니다.
"""
    + _SHARED_RULES
    + """
- 주어진 모든 requirement_id에 대해 하나씩 답합니다."""
)

SEMANTIC_SYSTEM = (
    """당신은 다른 심사관이 제시한 근거를 검증하는 검토자입니다.
각 항목의 인용문과, 그 인용문이 나온 이력서 줄(섹션 제목 포함)만 보고 요구조건 충족을 직접 확인할 수 있는지 판단합니다.
- 그 줄이 요구조건의 기술·경험을 본인이 직접 했다고 명시하면 supports=true입니다.
"""
    + _SHARED_RULES
    + """
- 다음은 supports=false입니다.
  * 다른 기술이나 경험을 말하고 있어 추측이 필요한 경우
    예: 요구조건 "SQL 활용 능력"에 "Pandas로 데이터를 정제했습니다" → false (SQL 언급이 없음)
  * 다른 사람·팀·외부 업체가 한 일, 검토만 하고 도입하지 않은 일, 관심·학습 중·교육 수료만 있는 경우
  * 요구하는 규모·기간·수준에 못 미치는 경우
- 이력서의 다른 부분은 고려하지 않습니다. 오직 주어진 줄만 봅니다."""
)


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


def span_feedback(quote: str, verdict: str, closest: str | None) -> str:
    """Retry feedback for a quote that is not verbatim in the resume.

    v3 told the model it could answer not_met instead, and it gave up on correct answers.
    v4 asks it to fix the quote and shows the closest real line; giving up is only for
    the case where no supporting line exists at all.
    """
    if not quote:
        head = f"{verdict}로 판정했지만 인용문이 비어 있습니다. 근거가 되는 이력서 줄을 그대로 복사하세요."
    else:
        head = (
            f'인용문 "{quote}"은(는) 이력서 원문과 글자가 다릅니다. 이력서의 한 줄 안에서, '
            "제목·회사명·날짜를 붙이지 말고 글자 그대로 복사하세요."
        )
    hint = f' 가장 비슷한 이력서 줄: "{closest}"' if closest else ""
    return head + hint + " 이력서 어디에도 근거가 없을 때만 판정을 not_met으로 바꾸세요."


def semantic_user(items: list[tuple[int, str, str, str]]) -> str:
    lines = ["[검증할 항목]"]
    for rid, requirement, quote, context in items:
        lines.append(
            f'- requirement_id={rid}\n  요구조건: {requirement}\n  인용문: "{quote}"\n  이력서 줄: "{context}"'
        )
    return "\n".join(lines)

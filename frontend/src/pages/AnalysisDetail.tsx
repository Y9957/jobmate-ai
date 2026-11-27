import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, api } from '../api'
import { ErrorBox, Loading, PageHead, StatusBadge, TypeBadge, VerdictBadge } from '../components'
import { useLoad } from '../hooks'
import type { Analysis, Evidence, RequirementType, Verdict } from '../types'
import { TYPE_LABEL, VERDICT_LABEL } from '../types'

export default function AnalysisDetail() {
  const id = Number(useParams().id)
  const { data, error, setData, reload } = useLoad(() => api.analysis(id), [id])
  const job = useLoad(async () => (data ? api.job(data.job_id) : null), [data?.job_id])
  const resume = useLoad(async () => (data ? api.resume(data.resume_id) : null), [data?.resume_id])

  // Poll while the background analysis is running
  const running = data?.status === 'pending' || data?.status === 'running'
  useEffect(() => {
    if (!running) return
    const t = setInterval(reload, 2500)
    return () => clearInterval(t)
  }, [running, reload])

  if (error) return <ErrorBox message={error} />
  if (!data) return <Loading />

  const title = job.data ? `${job.data.company} · ${job.data.title}` : '분석 결과'

  return (
    <>
      <PageHead title={title} sub={resume.data ? `이력서: ${resume.data.label}` : undefined}>
        <StatusBadge status={data.status} />
      </PageHead>

      {running && (
        <div className="card">
          <Loading text="로컬 모델로 분석 중입니다. 요구조건 추출 → 근거 매칭 → 원문 대조 → 의미 검증 순서로 진행돼요." />
        </div>
      )}
      {data.status === 'failed' && (
        <div className="alert bad">
          분석에 실패했습니다: {data.error}
          <br />
          로컬 모델(Ollama)이 켜져 있는지 확인한 뒤 <Link to="/analyses">다시 시도</Link>해 주세요.
        </div>
      )}

      {data.status === 'done' && (
        <>
          <Summary analysis={data} />
          {data.evidence.map((e) => (
            <EvidenceCard key={e.id} analysisId={data.id} evidence={e} onChange={setData} />
          ))}
          <p className="hint">
            모델 {data.model} · 프롬프트 {data.prompt_version}
            {data.pii_masked && Object.keys(data.pii_masked).length > 0 && ' · 연락처는 모델에 보내기 전에 가려졌습니다'}
          </p>
        </>
      )}
    </>
  )
}

function Summary({ analysis }: { analysis: Analysis }) {
  const kinds = (Object.keys(TYPE_LABEL) as RequirementType[]).filter((k) => analysis.coverage?.[k]?.total)
  const unverified = analysis.evidence.filter((e) => e.verdict === 'met' && e.semantic_verified === false).length
  return (
    <div className="card">
      <div className="coverage">
        {kinds.map((k) => (
          <div className="pill" key={k}>
            <div className="stat-label">{TYPE_LABEL[k]} 충족</div>
            <div className="num">
              {analysis.coverage![k].met} / {analysis.coverage![k].total}
            </div>
          </div>
        ))}
      </div>
      {analysis.warnings.map((w) => (
        <div className="alert warn" key={w} style={{ marginTop: 12, marginBottom: 0 }}>
          ⚠ {w}
        </div>
      ))}
      <p className="hint" style={{ marginTop: 12 }}>
        이 결과는 합격 가능성이 아니라, 이력서 문장으로 확인되는 요구조건이 몇 개인지를 보여줍니다.
        {unverified > 0 && ` 의미 검증을 통과하지 못한 항목 ${unverified}개가 있습니다.`}
      </p>
    </div>
  )
}

function EvidenceCard({
  analysisId,
  evidence: e,
  onChange,
}: {
  analysisId: number
  evidence: Evidence
  onChange: (a: Analysis) => void
}) {
  const [editing, setEditing] = useState(false)
  const [quote, setQuote] = useState(e.resume_quote ?? '')
  const [verdict, setVerdict] = useState<Verdict | ''>('')
  const [error, setError] = useState<string | null>(null)
  const [closest, setClosest] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true)
    setError(null)
    setClosest(null)
    try {
      onChange(await api.updateEvidence(analysisId, e.id, quote, verdict || undefined))
      setEditing(false)
    } catch (err) {
      setError((err as Error).message)
      if (err instanceof ApiError) setClosest((err.detail as { closest_line?: string })?.closest_line ?? null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`card evidence ${e.verdict}`}>
      <div className="evidence-head">
        <TypeBadge type={e.requirement_type} />
        <h3>{e.requirement}</h3>
        <VerdictBadge verdict={e.verdict} />
      </div>

      <dl className="quote-block">
        <dt>공고 원문</dt>
        <dd>
          {e.job_quote}{' '}
          {!e.job_quote_verified && <span className="badge warn">공고 원문에서 확인 안 됨</span>}
        </dd>
        <dt>이력서 근거</dt>
        <dd>{e.resume_quote ? <blockquote>{e.resume_quote}</blockquote> : <span className="muted">근거 문장 없음</span>}</dd>
        <dt>검증</dt>
        <dd className="checks">
          <span className={`badge ${e.span_verified ? 'ok' : ''}`}>원문 대조 {e.span_verified ? '통과' : '-'}</span>
          <span className={`badge ${e.semantic_verified ? 'ok' : e.semantic_verified === false ? 'bad' : ''}`}>
            의미 검증 {e.semantic_verified ? '통과' : e.semantic_verified === false ? '실패' : '-'}
          </span>
          {e.user_edited && <span className="badge accent">사용자 수정</span>}
        </dd>
        {e.explanation && (
          <>
            <dt>판정 이유</dt>
            <dd>{e.explanation}</dd>
          </>
        )}
      </dl>
      {!!e.notes?.length && (
        <ul className="notes">
          {e.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}

      {!editing ? (
        <div className="actions">
          <button type="button" className="secondary" onClick={() => setEditing(true)}>
            근거 수정
          </button>
        </div>
      ) : (
        <div style={{ marginTop: 12 }}>
          <ErrorBox message={error} />
          {closest && (
            <div className="alert info">
              가장 비슷한 이력서 줄: “{closest}”{' '}
              <button type="button" className="ghost" style={{ color: 'var(--accent)' }} onClick={() => setQuote(closest)}>
                이 줄 사용
              </button>
            </div>
          )}
          <label htmlFor={`q${e.id}`}>이력서 근거 문장 (원문 그대로 복사)</label>
          <textarea id={`q${e.id}`} value={quote} onChange={(ev) => setQuote(ev.target.value)} style={{ minHeight: 70 }} />
          <label htmlFor={`v${e.id}`}>판정</label>
          <select id={`v${e.id}`} value={verdict} onChange={(ev) => setVerdict(ev.target.value as Verdict | '')}>
            <option value="">자동 (근거가 있으면 충족)</option>
            {(Object.keys(VERDICT_LABEL) as Verdict[]).map((v) => (
              <option key={v} value={v}>
                {VERDICT_LABEL[v]}
              </option>
            ))}
          </select>
          <p className="hint">저장하면 원문 대조와 의미 검증을 다시 거칩니다. 검증을 통과하지 못하면 충족으로 인정되지 않습니다.</p>
          <div className="actions">
            <button type="button" onClick={save} disabled={busy}>
              {busy ? '검증 중…' : '저장하고 재검증'}
            </button>
            <button type="button" className="ghost" onClick={() => setEditing(false)}>
              취소
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

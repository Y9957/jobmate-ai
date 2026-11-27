import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { AnalysisStatus, AnalysisSummary, Coverage, RequirementType, Verdict } from './types'
import { TYPE_LABEL, VERDICT_LABEL } from './types'

export function PageHead({ title, sub, children }: { title: string; sub?: string; children?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <p>{sub}</p>}
      </div>
      {children}
    </div>
  )
}

export function Loading({ text = '불러오는 중…' }: { text?: string }) {
  return (
    <p className="muted">
      <span className="spinner" />
      {text}
    </p>
  )
}

export function ErrorBox({ message }: { message: string | null }) {
  return message ? <div className="alert bad">{message}</div> : null
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const tone = verdict === 'met' ? 'ok' : verdict === 'not_met' ? 'bad' : 'warn'
  return <span className={`badge ${tone}`}>{VERDICT_LABEL[verdict]}</span>
}

export function TypeBadge({ type }: { type: RequirementType }) {
  return <span className={`badge ${type === 'constraint' ? 'warn' : type === 'required' ? 'accent' : ''}`}>{TYPE_LABEL[type]}</span>
}

export function StatusBadge({ status }: { status: AnalysisStatus }) {
  const map: Record<AnalysisStatus, [string, string]> = {
    pending: ['대기', ''],
    running: ['분석 중', 'accent'],
    done: ['완료', 'ok'],
    failed: ['실패', 'bad'],
  }
  const [label, tone] = map[status]
  return <span className={`badge ${tone}`}>{label}</span>
}

export function CoverageLine({ coverage }: { coverage: Record<RequirementType, Coverage> | null }) {
  if (!coverage) return <span className="muted">-</span>
  return (
    <span>
      {(Object.keys(TYPE_LABEL) as RequirementType[])
        .filter((k) => coverage[k]?.total)
        .map((k) => `${TYPE_LABEL[k]} ${coverage[k].met}/${coverage[k].total}`)
        .join(' · ')}
    </span>
  )
}

export function AnalysisTable({ rows }: { rows: AnalysisSummary[] }) {
  if (!rows.length) return <p className="empty">아직 분석이 없습니다.</p>
  return (
    <table>
      <thead>
        <tr>
          <th>공고</th>
          <th>이력서</th>
          <th>충족 현황</th>
          <th>상태</th>
          <th>날짜</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((a) => (
          <tr key={a.id}>
            <td>
              <Link to={`/analyses/${a.id}`}>
                {a.company} · {a.job_title}
              </Link>
            </td>
            <td>{a.resume_label}</td>
            <td>
              <CoverageLine coverage={a.coverage} />
            </td>
            <td>
              <StatusBadge status={a.status} />
            </td>
            <td className="muted">{new Date(a.created_at).toLocaleDateString('ko-KR')}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

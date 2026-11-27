import { useState } from 'react'
import { api } from '../api'
import { ErrorBox, Loading, PageHead } from '../components'
import { fmtDate, useLoad } from '../hooks'
import type { ApplicationStage } from '../types'
import { STAGES, STAGE_LABEL } from '../types'

export default function Applications() {
  const list = useLoad(api.applications)
  const jobs = useLoad(api.jobs)
  const [jobId, setJobId] = useState('')
  const [stage, setStage] = useState<ApplicationStage>('interested')
  const [error, setError] = useState<string | null>(null)

  async function add() {
    setError(null)
    try {
      await api.createApplication(Number(jobId), stage)
      setJobId('')
      await list.reload()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  async function update(id: number, body: Parameters<typeof api.updateApplication>[1]) {
    setError(null)
    try {
      await api.updateApplication(id, body)
      await list.reload()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <>
      <PageHead title="지원 현황" sub="관심 → 지원 예정 → 지원 완료 → 서류 합격 → 면접 → 최종 결과 순서로 관리합니다." />
      <ErrorBox message={error} />

      <div className="card">
        <h2>지원 추가</h2>
        <div className="grid cols-2">
          <div>
            <label htmlFor="job">공고</label>
            <select id="job" value={jobId} onChange={(e) => setJobId(e.target.value)}>
              <option value="">선택</option>
              {jobs.data?.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.company} · {j.title}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="stage">단계</label>
            <select id="stage" value={stage} onChange={(e) => setStage(e.target.value as ApplicationStage)}>
              {STAGES.map((s) => (
                <option key={s} value={s}>
                  {STAGE_LABEL[s]}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="actions">
          <button type="button" onClick={add} disabled={!jobId}>
            추가
          </button>
        </div>
      </div>

      <div className="card">
        <h2>진행 중인 지원</h2>
        {list.loading && !list.data && <Loading />}
        {list.data && !list.data.length && <p className="empty">아직 지원 기록이 없습니다.</p>}
        {!!list.data?.length && (
          <table>
            <thead>
              <tr>
                <th>공고</th>
                <th style={{ width: 150 }}>단계</th>
                <th style={{ width: 160 }}>지원일</th>
                <th>메모</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.data.map((a) => (
                <tr key={a.id}>
                  <td>
                    {a.company} · {a.job_title}
                    <div className="hint">수정 {fmtDate(a.updated_at)}</div>
                  </td>
                  <td>
                    <select value={a.stage} onChange={(e) => update(a.id, { stage: e.target.value as ApplicationStage })}>
                      {STAGES.map((s) => (
                        <option key={s} value={s}>
                          {STAGE_LABEL[s]}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input type="date" value={a.applied_at ?? ''} onChange={(e) => update(a.id, { applied_at: e.target.value || null })} />
                  </td>
                  <td>
                    <input
                      defaultValue={a.notes ?? ''}
                      placeholder="메모"
                      onBlur={(e) => e.target.value !== (a.notes ?? '') && update(a.id, { notes: e.target.value || null })}
                    />
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button
                      type="button"
                      className="danger"
                      onClick={async () => {
                        if (confirm('이 지원 기록을 삭제할까요?')) {
                          await api.deleteApplication(a.id)
                          list.reload()
                        }
                      }}
                    >
                      삭제
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { AnalysisTable, ErrorBox, Loading, PageHead } from '../components'
import { useLoad } from '../hooks'

export default function Analyses() {
  const resumes = useLoad(api.resumes)
  const jobs = useLoad(api.jobs)
  const list = useLoad(api.analyses)
  const [resumeId, setResumeId] = useState('')
  const [jobId, setJobId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function start() {
    setBusy(true)
    setError(null)
    try {
      const a = await api.startAnalysis(Number(resumeId), Number(jobId))
      navigate(`/analyses/${a.id}`)
    } catch (e) {
      setError((e as Error).message)
      setBusy(false)
    }
  }

  const ready = resumes.data?.length && jobs.data?.length

  return (
    <>
      <PageHead title="분석" sub="공고의 요구조건마다 이력서 근거를 찾고, 그 근거가 원문에 있는지·조건을 뒷받침하는지 검증합니다." />

      <div className="card">
        <h2>새 분석</h2>
        <ErrorBox message={error} />
        {(resumes.loading || jobs.loading) && <Loading />}
        {!resumes.loading && !jobs.loading && !ready && (
          <div className="alert info">
            분석하려면 <Link to="/resumes">이력서</Link>와 <Link to="/jobs">공고</Link>를 하나 이상 등록해 주세요.
          </div>
        )}
        {!!ready && (
          <>
            <div className="grid cols-2">
              <div>
                <label htmlFor="resume">이력서</label>
                <select id="resume" value={resumeId} onChange={(e) => setResumeId(e.target.value)}>
                  <option value="">선택</option>
                  {resumes.data!.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="job">공고</label>
                <select id="job" value={jobId} onChange={(e) => setJobId(e.target.value)}>
                  <option value="">선택</option>
                  {jobs.data!.map((j) => (
                    <option key={j.id} value={j.id}>
                      {j.company} · {j.title}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="actions">
              <button type="button" onClick={start} disabled={busy || !resumeId || !jobId}>
                분석 시작
              </button>
              <span className="hint">로컬 모델 기준 공고 1건에 20~40초 정도 걸립니다.</span>
            </div>
          </>
        )}
      </div>

      <div className="card">
        <h2>분석 기록</h2>
        <ErrorBox message={list.error} />
        {list.loading && !list.data && <Loading />}
        {list.data && <AnalysisTable rows={list.data} />}
      </div>
    </>
  )
}

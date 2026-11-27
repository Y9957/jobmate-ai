import { Link } from 'react-router-dom'
import { api } from '../api'
import { AnalysisTable, ErrorBox, Loading, PageHead } from '../components'
import { useLoad } from '../hooks'
import { STAGES, STAGE_LABEL } from '../types'

export default function Dashboard() {
  const { data, error, loading } = useLoad(api.dashboard)

  return (
    <>
      <PageHead title="대시보드" sub="이력서와 공고를 대조한 분석, 지원 진행 상황을 한눈에 봅니다." />
      <ErrorBox message={error} />
      {loading && !data && <Loading />}
      {data && (
        <>
          <div className="grid cols-3">
            <Link to="/resumes" className="card">
              <div className="stat">{data.resumes}</div>
              <div className="stat-label">등록한 이력서</div>
            </Link>
            <Link to="/jobs" className="card">
              <div className="stat">{data.jobs}</div>
              <div className="stat-label">등록한 공고</div>
            </Link>
            <Link to="/analyses" className="card">
              <div className="stat">{data.analyses}</div>
              <div className="stat-label">분석</div>
            </Link>
          </div>

          <div className="card">
            <div className="row">
              <h2>지원 현황</h2>
              <Link to="/applications">관리하기 →</Link>
            </div>
            <div className="grid cols-4" style={{ marginTop: 12 }}>
              {STAGES.map((s) => (
                <div key={s}>
                  <div className="stat" style={{ fontSize: 20 }}>
                    {data.applications_by_stage[s] ?? 0}
                  </div>
                  <div className="stat-label">{STAGE_LABEL[s]}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="row" style={{ marginBottom: 6 }}>
              <h2>최근 분석</h2>
              <Link to="/analyses">새 분석 →</Link>
            </div>
            <AnalysisTable rows={data.recent_analyses} />
          </div>
        </>
      )}
    </>
  )
}

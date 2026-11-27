import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import AnalysisDetail from './pages/AnalysisDetail'
import Analyses from './pages/Analyses'
import Applications from './pages/Applications'
import Dashboard from './pages/Dashboard'
import Jobs from './pages/Jobs'
import Resumes from './pages/Resumes'

const NAV = [
  ['/', '대시보드'],
  ['/resumes', '이력서'],
  ['/jobs', '채용공고'],
  ['/analyses', '분석'],
  ['/applications', '지원 현황'],
] as const

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <aside className="sidebar">
          <div className="brand">JobMate AI</div>
          <div className="brand-sub">근거로 검증하는 공고 적합성 분석</div>
          <nav className="nav">
            {NAV.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === '/'}>
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-foot">
            로컬 LLM으로 분석합니다.
            <br />
            <a href="https://github.com/Y9957/jobmate-ai" target="_blank" rel="noreferrer">
              GitHub
            </a>
          </div>
        </aside>
        <main className="main">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/resumes" element={<Resumes />} />
            <Route path="/jobs" element={<Jobs />} />
            <Route path="/analyses" element={<Analyses />} />
            <Route path="/analyses/:id" element={<AnalysisDetail />} />
            <Route path="/applications" element={<Applications />} />
            <Route path="*" element={<p className="empty">페이지를 찾을 수 없습니다.</p>} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

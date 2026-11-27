import { useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import { ErrorBox, Loading, PageHead } from '../components'
import { fmtDate, useLoad } from '../hooks'
import type { Job } from '../types'

const empty = { company: '', title: '', description: '', source_url: '', deadline: '' }

export default function Jobs() {
  const list = useLoad(api.jobs)
  const [form, setForm] = useState(empty)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState<Job | null>(null)
  const set = (k: keyof typeof empty) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value })

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.createJob({
        company: form.company,
        title: form.title,
        description: form.description,
        source_url: form.source_url || undefined,
        deadline: form.deadline || undefined,
      })
      setForm(empty)
      await list.reload()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHead title="채용공고" sub="공고 본문을 직접 붙여넣습니다. 링크는 기록만 하고 자동으로 가져오지 않습니다." />

      <form className="card" onSubmit={onSubmit}>
        <h2>공고 등록</h2>
        <ErrorBox message={error} />
        <div className="grid cols-2">
          <div>
            <label htmlFor="company">회사</label>
            <input id="company" value={form.company} onChange={set('company')} required maxLength={100} />
          </div>
          <div>
            <label htmlFor="title">포지션</label>
            <input id="title" value={form.title} onChange={set('title')} required maxLength={200} />
          </div>
          <div>
            <label htmlFor="url">공고 링크 (선택)</label>
            <input id="url" type="url" value={form.source_url} onChange={set('source_url')} placeholder="https://" />
          </div>
          <div>
            <label htmlFor="deadline">마감일 (선택)</label>
            <input id="deadline" type="date" value={form.deadline} onChange={set('deadline')} />
          </div>
        </div>
        <label htmlFor="desc">공고 본문</label>
        <textarea id="desc" value={form.description} onChange={set('description')} required minLength={20} style={{ minHeight: 220 }} placeholder="자격 요건, 우대 사항이 포함된 공고 본문을 붙여넣으세요." />
        <div className="actions">
          <button type="submit" disabled={busy}>
            저장
          </button>
        </div>
      </form>

      <div className="card">
        <h2>등록한 공고</h2>
        <ErrorBox message={list.error} />
        {list.loading && !list.data && <Loading />}
        {list.data && !list.data.length && <p className="empty">아직 등록한 공고가 없습니다.</p>}
        {!!list.data?.length && (
          <table>
            <thead>
              <tr>
                <th>회사 · 포지션</th>
                <th>마감</th>
                <th>등록일</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.data.map((j) => (
                <tr key={j.id}>
                  <td>
                    <button type="button" className="ghost" style={{ color: 'var(--accent)', padding: 0 }} onClick={async () => setOpen(await api.job(j.id))}>
                      {j.company} · {j.title}
                    </button>
                  </td>
                  <td>{j.deadline ?? <span className="muted">-</span>}</td>
                  <td className="muted">{fmtDate(j.created_at)}</td>
                  <td style={{ textAlign: 'right' }}>
                    <button
                      type="button"
                      className="danger"
                      onClick={async () => {
                        if (confirm(`"${j.title}" 공고와 관련 분석·지원 기록을 삭제할까요?`)) {
                          await api.deleteJob(j.id)
                          if (open?.id === j.id) setOpen(null)
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

      {open && (
        <div className="card">
          <div className="row">
            <h2>
              {open.company} · {open.title}
            </h2>
            <button type="button" className="ghost" onClick={() => setOpen(null)}>
              닫기
            </button>
          </div>
          {open.source_url && (
            <p>
              <a href={open.source_url} target="_blank" rel="noreferrer">
                원본 공고
              </a>{' '}
              <span className="badge warn">접수 상태 확인되지 않음</span>
            </p>
          )}
          <pre className="resume">{open.description}</pre>
        </div>
      )}
    </>
  )
}

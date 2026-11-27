import { useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import { ErrorBox, Loading, PageHead } from '../components'
import { fmtDate, useLoad } from '../hooks'
import type { Resume } from '../types'

const PII_LABEL: Record<string, string> = { email: '이메일', phone: '전화번호', rrn: '주민등록번호' }

export default function Resumes() {
  const list = useLoad(api.resumes)
  const [label, setLabel] = useState('')
  const [text, setText] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState<Resume | null>(null)

  async function onPdf(file: File | undefined) {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const r = await api.extractPdf(file)
      setText(r.text)
      if (!label) setLabel(file.name.replace(/\.pdf$/i, ''))
      const found = Object.entries(r.pii_found).map(([k, n]) => `${PII_LABEL[k] ?? k} ${n}건`)
      setNotice(
        `${r.pages}쪽에서 텍스트를 추출했습니다. ${r.note}` +
          (found.length ? ` 연락처(${found.join(', ')})는 저장할 때 가려집니다.` : ''),
      )
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.createResume(label, text)
      setLabel('')
      setText('')
      setNotice(null)
      await list.reload()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHead title="이력서" sub="이메일·전화번호·주민번호는 저장 전에 가려지고, 원본 PDF는 저장하지 않습니다." />

      <form className="card" onSubmit={onSubmit}>
        <h2>이력서 등록</h2>
        <ErrorBox message={error} />
        {notice && <div className="alert info">{notice}</div>}
        <label htmlFor="pdf">PDF에서 불러오기 (선택)</label>
        <input id="pdf" type="file" accept="application/pdf" onChange={(e) => onPdf(e.target.files?.[0])} disabled={busy} />
        <p className="hint">텍스트로 된 PDF만 지원합니다. 스캔한 이미지 PDF는 내용을 직접 붙여넣어 주세요.</p>

        <label htmlFor="label">이름</label>
        <input id="label" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="예: 백엔드 지원용" required maxLength={100} />

        <label htmlFor="text">이력서 내용</label>
        <textarea id="text" value={text} onChange={(e) => setText(e.target.value)} required minLength={20} style={{ minHeight: 260 }} placeholder="이력서 내용을 붙여넣거나 PDF에서 불러오세요." />
        <p className="hint">공개 데모에서는 실제 이력서 대신 가상 이력서를 사용해 주세요.</p>

        <div className="actions">
          <button type="submit" disabled={busy || !label || text.length < 20}>
            저장
          </button>
          {busy && <Loading text="처리 중…" />}
        </div>
      </form>

      <div className="card">
        <h2>등록한 이력서</h2>
        <ErrorBox message={list.error} />
        {list.loading && !list.data && <Loading />}
        {list.data && !list.data.length && <p className="empty">아직 등록한 이력서가 없습니다.</p>}
        {!!list.data?.length && (
          <table>
            <thead>
              <tr>
                <th>이름</th>
                <th>등록일</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.data.map((r) => (
                <tr key={r.id}>
                  <td>
                    <button type="button" className="ghost" style={{ color: 'var(--accent)', padding: 0 }} onClick={async () => setOpen(await api.resume(r.id))}>
                      {r.label}
                    </button>{' '}
                    {r.is_sample && <span className="badge">샘플</span>}
                  </td>
                  <td className="muted">{fmtDate(r.created_at)}</td>
                  <td style={{ textAlign: 'right' }}>
                    <button
                      type="button"
                      className="danger"
                      onClick={async () => {
                        if (confirm(`"${r.label}" 이력서와 관련 분석을 삭제할까요?`)) {
                          await api.deleteResume(r.id)
                          if (open?.id === r.id) setOpen(null)
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
            <h2>{open.label} — 저장된 내용 (마스킹 후)</h2>
            <button type="button" className="ghost" onClick={() => setOpen(null)}>
              닫기
            </button>
          </div>
          <pre className="resume" style={{ marginTop: 12 }}>
            {open.masked_text}
          </pre>
        </div>
      )}
    </>
  )
}

import type {
  Analysis,
  AnalysisSummary,
  Application,
  ApplicationStage,
  Dashboard,
  ExtractedText,
  Job,
  JobSummary,
  Resume,
  ResumeSummary,
  Verdict,
} from './types'

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : (detail as { message?: string })?.message ?? `요청 실패 (${status})`)
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (res.status === 204) return undefined as T
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = body?.detail
    // FastAPI validation errors come back as a list
    if (Array.isArray(detail)) throw new ApiError(res.status, detail.map((d) => d.msg).join(', '))
    throw new ApiError(res.status, detail ?? `요청 실패 (${res.status})`)
  }
  return body as T
}

const json = (body: unknown) => ({ body: JSON.stringify(body) })

export const api = {
  dashboard: () => request<Dashboard>('/api/dashboard'),

  resumes: () => request<ResumeSummary[]>('/api/resumes'),
  resume: (id: number) => request<Resume>(`/api/resumes/${id}`),
  createResume: (label: string, text: string) =>
    request<Resume>('/api/resumes', { method: 'POST', ...json({ label, text }) }),
  deleteResume: (id: number) => request<void>(`/api/resumes/${id}`, { method: 'DELETE' }),
  extractPdf: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<ExtractedText>('/api/resumes/extract', { method: 'POST', body: form })
  },

  jobs: () => request<JobSummary[]>('/api/jobs'),
  job: (id: number) => request<Job>(`/api/jobs/${id}`),
  createJob: (body: { company: string; title: string; description: string; source_url?: string; deadline?: string }) =>
    request<Job>('/api/jobs', { method: 'POST', ...json(body) }),
  deleteJob: (id: number) => request<void>(`/api/jobs/${id}`, { method: 'DELETE' }),

  analyses: () => request<AnalysisSummary[]>('/api/analyses'),
  analysis: (id: number) => request<Analysis>(`/api/analyses/${id}`),
  startAnalysis: (resume_id: number, job_id: number) =>
    request<Analysis>('/api/analyses', { method: 'POST', ...json({ resume_id, job_id }) }),
  updateEvidence: (analysisId: number, evidenceId: number, resume_quote: string, verdict?: Verdict) =>
    request<Analysis>(`/api/analyses/${analysisId}/evidence/${evidenceId}`, {
      method: 'PATCH',
      ...json({ resume_quote, verdict }),
    }),
  deleteAnalysis: (id: number) => request<void>(`/api/analyses/${id}`, { method: 'DELETE' }),

  applications: () => request<Application[]>('/api/applications'),
  createApplication: (job_id: number, stage: ApplicationStage) =>
    request<Application>('/api/applications', { method: 'POST', ...json({ job_id, stage }) }),
  updateApplication: (id: number, body: { stage?: ApplicationStage; applied_at?: string | null; notes?: string | null }) =>
    request<Application>(`/api/applications/${id}`, { method: 'PATCH', ...json(body) }),
  deleteApplication: (id: number) => request<void>(`/api/applications/${id}`, { method: 'DELETE' }),
}

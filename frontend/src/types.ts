// Mirrors backend/app/api/schemas.py

export type RequirementType = 'required' | 'preferred' | 'constraint'
export type Verdict = 'met' | 'not_met' | 'insufficient'
export type AnalysisStatus = 'pending' | 'running' | 'done' | 'failed'
export type ApplicationStage =
  | 'interested'
  | 'planned'
  | 'applied'
  | 'document_passed'
  | 'interview'
  | 'offer'
  | 'rejected'
  | 'withdrawn'

export interface ResumeSummary {
  id: number
  label: string
  is_sample: boolean
  created_at: string
}

export interface Resume extends ResumeSummary {
  masked_text: string
}

export interface ExtractedText {
  text: string
  pages: number
  pii_found: Record<string, number>
  note: string
}

export interface JobSummary {
  id: number
  company: string
  title: string
  deadline: string | null
  created_at: string
}

export interface Job extends JobSummary {
  description: string
  source_url: string | null
  source_status_checked: boolean
}

export interface Coverage {
  met: number
  total: number
}

export interface Evidence {
  id: number
  position: number
  requirement: string
  requirement_type: RequirementType
  job_quote: string | null
  job_quote_verified: boolean
  resume_quote: string | null
  verdict: Verdict
  span_verified: boolean
  semantic_verified: boolean | null
  explanation: string | null
  notes: string[] | null
  user_edited: boolean
}

export interface Analysis {
  id: number
  resume_id: number
  job_id: number
  status: AnalysisStatus
  coverage: Record<RequirementType, Coverage> | null
  warnings: string[]
  model: string | null
  prompt_version: string | null
  error: string | null
  pii_masked: Record<string, number> | null
  trace: string[] | null
  created_at: string
  finished_at: string | null
  evidence: Evidence[]
}

export interface AnalysisSummary {
  id: number
  status: AnalysisStatus
  resume_id: number
  resume_label: string
  job_id: number
  job_title: string
  company: string
  coverage: Record<RequirementType, Coverage> | null
  created_at: string
}

export interface Application {
  id: number
  job_id: number
  stage: ApplicationStage
  applied_at: string | null
  notes: string | null
  updated_at: string
  company: string
  job_title: string
}

export interface Dashboard {
  resumes: number
  jobs: number
  analyses: number
  applications_by_stage: Record<ApplicationStage, number>
  recent_analyses: AnalysisSummary[]
}

export const TYPE_LABEL: Record<RequirementType, string> = {
  required: '필수',
  preferred: '우대',
  constraint: '제한 조건',
}

export const VERDICT_LABEL: Record<Verdict, string> = {
  met: '충족',
  not_met: '미충족',
  insufficient: '근거 부족',
}

export const STAGE_LABEL: Record<ApplicationStage, string> = {
  interested: '관심',
  planned: '지원 예정',
  applied: '지원 완료',
  document_passed: '서류 합격',
  interview: '면접',
  offer: '최종 합격',
  rejected: '불합격',
  withdrawn: '지원 철회',
}

export const STAGES = Object.keys(STAGE_LABEL) as ApplicationStage[]

export interface WechatLoginRequest {
  code: string
}

export interface WechatLoginResponse {
  access_token: string
  is_new_user: boolean
}

export interface HealthProfile {
  allergens: string[]
  chronic_diseases: string[]
}

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH'

export interface AnalysisResult {
  answer: string
  reference: string[]
}

export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface AnalyzeTaskResponse {
  task_id: string
  status: Extract<TaskStatus, 'pending'>
}

export type TaskStatusResponse =
  | { status: 'processing' }
  | { status: 'completed'; result: AnalysisResult }
  | { status: 'failed'; error?: string }

export interface HistoryRecord {
  task_id: string
  food_name: string
  risk_level: RiskLevel
  created_at: string
}

export interface HistoryListResponse {
  total: number
  records: HistoryRecord[]
}

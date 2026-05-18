import { MOCK_LATENCY_MS, TASK_PROCESSING_MS } from '../config/env'
import type {
  AnalysisResult,
  AnalyzeTaskResponse,
  HealthProfile,
  HistoryListResponse,
  TaskStatusResponse,
  WechatLoginResponse,
} from '../types/api'
import { ApiError } from '../utils/api-error'

type MockHandler = (params: {
  path: string
  query: Record<string, string>
  body: unknown
  pathParams: Record<string, string>
}) => unknown | Promise<unknown>

interface Route {
  method: string
  pattern: RegExp
  paramNames: string[]
  handler: MockHandler
}

function compile(method: string, template: string, handler: MockHandler): Route {
  const paramNames: string[] = []
  const regex = template.replace(/\{(\w+)\}/g, (_, name) => {
    paramNames.push(name)
    return '([^/]+)'
  })
  return {
    method,
    pattern: new RegExp(`^${regex}$`),
    paramNames,
    handler,
  }
}

const profile: HealthProfile = {
  allergens: ['海鲜', '花生'],
  chronic_diseases: ['2型糖尿病'],
}

const taskSubmittedAt = new Map<string, number>()

const sampleResult: AnalysisResult = {
  food_name: '某品牌夹心饼干',
  ingredients: ['小麦粉', '白砂糖', '代可可脂', '棕榈油', '食用盐'],
  risk_level: 'HIGH',
  health_advice:
    '该食品含糖量极高且含有代可可脂，违反《糖尿病医学营养治疗指南》，建议避免食用。',
  tts_audio_url: 'https://oss-bucket.example.com/audio/sample.mp3',
}

const historyRecords = [
  {
    task_id: 'hist-001',
    food_name: '纯牛奶',
    risk_level: 'LOW' as const,
    created_at: '2026-05-17T10:00:00Z',
  },
  {
    task_id: 'hist-002',
    food_name: '可乐',
    risk_level: 'HIGH' as const,
    created_at: '2026-05-16T09:30:00Z',
  },
  {
    task_id: 'hist-003',
    food_name: '燕麦片',
    risk_level: 'LOW' as const,
    created_at: '2026-05-15T08:15:00Z',
  },
  {
    task_id: 'hist-004',
    food_name: '薯片',
    risk_level: 'MEDIUM' as const,
    created_at: '2026-05-14T19:42:00Z',
  },
]

function uuid(): string {
  return 'mock-' + Math.random().toString(36).slice(2, 10) + '-' + Date.now().toString(36)
}

const routes: Route[] = [
  compile('POST', '/auth/wechat-login', () => {
    const resp: WechatLoginResponse = {
      access_token: 'mock-jwt-' + uuid(),
      is_new_user: false,
    }
    return resp
  }),

  compile('GET', '/users/me/profile', () => profile),

  compile('PUT', '/users/me/profile', ({ body }) => {
    const next = body as Partial<HealthProfile>
    if (Array.isArray(next.allergens)) profile.allergens = next.allergens
    if (Array.isArray(next.chronic_diseases)) profile.chronic_diseases = next.chronic_diseases
    return null
  }),

  compile('POST', '/tasks/analyze', () => {
    const task_id = uuid()
    taskSubmittedAt.set(task_id, Date.now())
    const resp: AnalyzeTaskResponse = { task_id, status: 'pending' }
    return resp
  }),

  compile('GET', '/tasks/{task_id}/status', ({ pathParams }) => {
    const id = pathParams.task_id
    const submittedAt = taskSubmittedAt.get(id)
    if (submittedAt === undefined) {
      throw new ApiError(404, 'task not found', { task_id: id })
    }
    const elapsed = Date.now() - submittedAt
    if (elapsed < TASK_PROCESSING_MS) {
      const resp: TaskStatusResponse = { status: 'processing' }
      return resp
    }
    const resp: TaskStatusResponse = { status: 'completed', result: sampleResult }
    return resp
  }),

  compile('GET', '/users/me/history', ({ query }) => {
    const page = Number(query.page ?? '1') || 1
    const size = Number(query.size ?? '10') || 10
    const start = (page - 1) * size
    const resp: HistoryListResponse = {
      total: historyRecords.length,
      records: historyRecords.slice(start, start + size),
    }
    return resp
  }),
]

function parseUrl(url: string): { path: string; query: Record<string, string> } {
  const [path, qs] = url.split('?')
  const query: Record<string, string> = {}
  if (qs) {
    for (const pair of qs.split('&')) {
      const [k, v = ''] = pair.split('=')
      if (k) query[decodeURIComponent(k)] = decodeURIComponent(v)
    }
  }
  return { path, query }
}

export function mockRequest<T>(
  url: string,
  method: string,
  body: unknown,
): Promise<T> {
  const { path, query } = parseUrl(url)

  return new Promise((resolve, reject) => {
    setTimeout(() => {
      for (const route of routes) {
        if (route.method !== method) continue
        const m = route.pattern.exec(path)
        if (!m) continue

        const pathParams: Record<string, string> = {}
        route.paramNames.forEach((name, i) => {
          pathParams[name] = decodeURIComponent(m[i + 1])
        })

        try {
          const result = route.handler({ path, query, body, pathParams })
          Promise.resolve(result).then(
            (r) => resolve(r as T),
            (e) => reject(e),
          )
        } catch (e) {
          reject(e)
        }
        return
      }
      reject(new ApiError(404, `mock route not found: ${method} ${path}`, null))
    }, MOCK_LATENCY_MS)
  })
}

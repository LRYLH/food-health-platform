import { BASE_URL, USE_MOCK } from '../config/env'
import { mockRequest } from '../mocks'
import { ApiError } from './api-error'
import { getToken } from './storage'

export { ApiError }

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'

export interface RequestOptions {
  url: string
  method?: HttpMethod
  data?: Record<string, unknown> | unknown[]
  query?: Record<string, string | number | undefined>
}

export interface UploadOptions {
  url: string
  filePath: string
  fileFormKey?: string
  formData?: Record<string, string>
}

function buildUrl(url: string, query?: RequestOptions['query']): string {
  if (!query) return url
  const parts: string[] = []
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined) continue
    parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
  }
  if (parts.length === 0) return url
  return `${url}${url.includes('?') ? '&' : '?'}${parts.join('&')}`
}

function authHeader(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function request<T>(opts: RequestOptions): Promise<T> {
  const method = opts.method ?? 'GET'
  const fullPath = buildUrl(opts.url, opts.query)

  if (USE_MOCK) {
    return mockRequest<T>(fullPath, method, opts.data)
  }

  return new Promise<T>((resolve, reject) => {
    uni.request({
      url: BASE_URL + fullPath,
      method,
      data: opts.data as Record<string, unknown> | undefined,
      header: { 'Content-Type': 'application/json', ...authHeader() },
      success: (res) => {
        const code = res.statusCode ?? 0
        if (code >= 200 && code < 300) {
          resolve(res.data as T)
        } else {
          reject(new ApiError(code, `HTTP ${code}`, res.data))
        }
      },
      fail: (err) => reject(new ApiError(0, err.errMsg ?? 'network error', err)),
    })
  })
}

export function upload<T>(opts: UploadOptions): Promise<T> {
  if (USE_MOCK) {
    return mockRequest<T>(opts.url, 'POST', opts.formData)
  }

  return new Promise<T>((resolve, reject) => {
    uni.uploadFile({
      url: BASE_URL + opts.url,
      filePath: opts.filePath,
      name: opts.fileFormKey ?? 'image',
      formData: opts.formData,
      header: authHeader(),
      success: (res) => {
        const code = res.statusCode ?? 0
        if (code >= 200 && code < 300) {
          try {
            resolve(JSON.parse(res.data) as T)
          } catch (e) {
            reject(new ApiError(code, 'invalid JSON response', res.data))
          }
        } else {
          reject(new ApiError(code, `HTTP ${code}`, res.data))
        }
      },
      fail: (err) => reject(new ApiError(0, err.errMsg ?? 'upload failed', err)),
    })
  })
}

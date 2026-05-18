import type { HistoryListResponse } from '../types/api'
import { request } from '../utils/request'

export function getHistory(params: { page?: number; size?: number } = {}): Promise<HistoryListResponse> {
  return request<HistoryListResponse>({
    url: '/users/me/history',
    method: 'GET',
    query: { page: params.page ?? 1, size: params.size ?? 10 },
  })
}

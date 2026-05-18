import type { AnalyzeTaskResponse, TaskStatusResponse } from '../types/api'
import { request, upload } from '../utils/request'

export function submitAnalysis(params: {
  imagePath: string
  voiceQuery?: string
}): Promise<AnalyzeTaskResponse> {
  return upload<AnalyzeTaskResponse>({
    url: '/tasks/analyze',
    filePath: params.imagePath,
    fileFormKey: 'image',
    formData: params.voiceQuery ? { voice_query: params.voiceQuery } : undefined,
  })
}

export function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  return request<TaskStatusResponse>({
    url: `/tasks/${encodeURIComponent(taskId)}/status`,
    method: 'GET',
  })
}

export async function pollUntilDone(
  taskId: string,
  opts: { intervalMs?: number; timeoutMs?: number } = {},
): Promise<TaskStatusResponse> {
  const interval = opts.intervalMs ?? 1000
  const timeout = opts.timeoutMs ?? 60_000
  const deadline = Date.now() + timeout

  while (Date.now() < deadline) {
    const resp = await getTaskStatus(taskId)
    if (resp.status !== 'processing') return resp
    await new Promise((r) => setTimeout(r, interval))
  }
  throw new Error(`task ${taskId} timed out after ${timeout}ms`)
}

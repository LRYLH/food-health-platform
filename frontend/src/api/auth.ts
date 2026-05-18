import type { WechatLoginRequest, WechatLoginResponse } from '../types/api'
import { request } from '../utils/request'
import { setToken } from '../utils/storage'

export async function loginByWechat(code: string): Promise<WechatLoginResponse> {
  const body: WechatLoginRequest = { code }
  const resp = await request<WechatLoginResponse>({
    url: '/auth/wechat-login',
    method: 'POST',
    data: body as unknown as Record<string, unknown>,
  })
  setToken(resp.access_token)
  return resp
}

import type { HealthProfile } from '../types/api'
import { request } from '../utils/request'

export function getProfile(): Promise<HealthProfile> {
  return request<HealthProfile>({ url: '/users/me/profile', method: 'GET' })
}

export function updateProfile(profile: HealthProfile): Promise<null> {
  return request<null>({
    url: '/users/me/profile',
    method: 'PUT',
    data: profile as unknown as Record<string, unknown>,
  })
}

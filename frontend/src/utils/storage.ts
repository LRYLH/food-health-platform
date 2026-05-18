const TOKEN_KEY = 'access_token'

export function getToken(): string {
  try {
    return (uni.getStorageSync(TOKEN_KEY) as string) || ''
  } catch {
    return ''
  }
}

export function setToken(token: string): void {
  uni.setStorageSync(TOKEN_KEY, token)
}

export function clearToken(): void {
  uni.removeStorageSync(TOKEN_KEY)
}

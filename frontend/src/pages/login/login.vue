<template>
  <view class="login-page" :style="rootStyle">
    <view class="hero">
      <view class="logo">食</view>
      <view class="app-name">食品安全与健康助手</view>
      <view class="tagline">拍照即扫，开口即懂</view>
    </view>

    <view class="status-area">
      <view v-if="status === 'loading'" class="status-block">
        <view class="spinner" />
        <text class="status-text">正在登录...</text>
      </view>

      <view v-else-if="status === 'success'" class="status-block">
        <text class="status-text success">登录成功，正在跳转...</text>
      </view>

      <view v-else class="status-block">
        <button class="login-btn" @tap="handleLogin">
          {{ status === 'error' ? '重试登录' : '微信一键登录' }}
        </button>
        <text v-if="errorMsg" class="error-msg">{{ errorMsg }}</text>
        <text class="hint">登录代表同意《用户协议》与《隐私政策》</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { loginByWechat } from '@/api/auth'
import { useSettings } from '@/store/settings'
import { getToken } from '@/utils/storage'

const { rootStyle } = useSettings()

type Status = 'idle' | 'loading' | 'success' | 'error'

const status = ref<Status>('idle')
const errorMsg = ref('')

async function handleLogin() {
  status.value = 'loading'
  errorMsg.value = ''

  try {
    const loginRes = await uni.login({ provider: 'weixin' })
    if (!loginRes.code) {
      throw new Error('未获取到微信授权 code')
    }

    await loginByWechat(loginRes.code)
    status.value = 'success'

    setTimeout(() => {
      uni.reLaunch({ url: '/pages/index/index' })
    }, 400)
  } catch (e) {
    status.value = 'error'
    errorMsg.value = e instanceof Error ? e.message : '登录失败，请重试'
  }
}

onMounted(() => {
  if (getToken()) {
    uni.reLaunch({ url: '/pages/index/index' })
    return
  }
  handleLogin()
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 160rpx 60rpx 80rpx;
  background: linear-gradient(180deg, #fff 0%, #f6f8fb 100%);
  box-sizing: border-box;
}

.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 160rpx;
}

.logo {
  width: 180rpx;
  height: 180rpx;
  border-radius: 36rpx;
  background: linear-gradient(135deg, #4caf50 0%, #2e7d32 100%);
  color: #fff;
  font-size: calc(96rpx * var(--font-scale, 1));
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 48rpx;
  box-shadow: 0 12rpx 32rpx rgba(46, 125, 50, 0.25);
}

.app-name {
  font-size: calc(44rpx * var(--font-scale, 1));
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 16rpx;
}

.tagline {
  font-size: calc(28rpx * var(--font-scale, 1));
  color: #8a8a8a;
  letter-spacing: 2rpx;
}

.status-area {
  width: 100%;
  display: flex;
  justify-content: center;
}

.status-block {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.spinner {
  width: 56rpx;
  height: 56rpx;
  border: 6rpx solid #e0e0e0;
  border-top-color: #4caf50;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 24rpx;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.status-text {
  font-size: calc(28rpx * var(--font-scale, 1));
  color: #666;
}

.status-text.success {
  color: #2e7d32;
}

.login-btn {
  width: 100%;
  height: 96rpx;
  line-height: 96rpx;
  background: #07c160;
  color: #fff;
  font-size: calc(32rpx * var(--font-scale, 1));
  font-weight: 500;
  border-radius: 16rpx;
}

.login-btn[disabled] {
  opacity: 0.6;
}

.error-msg {
  margin-top: 32rpx;
  font-size: calc(26rpx * var(--font-scale, 1));
  color: #e53935;
  text-align: center;
}

.hint {
  margin-top: 48rpx;
  font-size: calc(24rpx * var(--font-scale, 1));
  color: #999;
  text-align: center;
}
</style>

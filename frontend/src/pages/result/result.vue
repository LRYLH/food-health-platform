<template>
  <view class="result-page">
    <view v-if="status === 'loading'" class="loading-block">
      <view class="spinner" />
      <text class="loading-text">正在分析中...</text>
      <text class="loading-sub">通常需要几秒，请稍候</text>
    </view>

    <view v-else-if="status === 'failed'" class="failed-block">
      <text class="failed-icon">⚠</text>
      <text class="failed-text">分析失败</text>
      <text class="failed-sub">{{ errorMsg }}</text>
      <view class="retry-btn" @tap="goBack">
        <text>返回重试</text>
      </view>
    </view>

    <template v-else-if="status === 'completed' && result">
      <view class="hero-card" :class="riskClass(result.risk_level)">
        <text class="risk-tag">{{ riskLabel(result.risk_level) }}</text>
        <text class="food-name">{{ result.food_name }}</text>
      </view>

      <view class="section">
        <text class="section-title">配料表</text>
        <view class="chip-list">
          <view v-for="(ing, i) in result.ingredients" :key="i" class="chip">
            <text>{{ ing }}</text>
          </view>
        </view>
      </view>

      <view class="section">
        <text class="section-title">健康建议</text>
        <view class="advice-card">
          <text class="advice-text">{{ result.health_advice }}</text>
        </view>
      </view>

      <view v-if="result.tts_audio_url" class="section">
        <view class="tts-btn" @tap="playTts">
          <text>{{ playing ? '⏸ 停止语音播报' : '▶ 语音播报建议' }}</text>
        </view>
      </view>

      <view class="footer-actions">
        <view class="action-btn primary" @tap="goHome">
          <text>继续扫描</text>
        </view>
        <view class="action-btn" @tap="goHistory">
          <text>查看历史</text>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app'
import { ref } from 'vue'
import { pollUntilDone } from '@/api/tasks'
import type { AnalysisResult, RiskLevel } from '@/types/api'

type Status = 'loading' | 'completed' | 'failed'

const status = ref<Status>('loading')
const result = ref<AnalysisResult | null>(null)
const errorMsg = ref('')
const playing = ref(false)
let audioCtx: UniApp.InnerAudioContext | null = null

function riskLabel(level: RiskLevel): string {
  return { LOW: '低风险', MEDIUM: '中等风险', HIGH: '高风险' }[level]
}

function riskClass(level: RiskLevel): string {
  return `risk-${level.toLowerCase()}`
}

async function loadResult(taskId: string) {
  status.value = 'loading'
  try {
    const resp = await pollUntilDone(taskId, { intervalMs: 800, timeoutMs: 30_000 })
    if (resp.status === 'completed') {
      result.value = resp.result
      status.value = 'completed'
    } else if (resp.status === 'failed') {
      errorMsg.value = resp.error
      status.value = 'failed'
    }
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '未知错误'
    status.value = 'failed'
  }
}

function playTts() {
  if (!result.value?.tts_audio_url) return
  if (playing.value && audioCtx) {
    audioCtx.stop()
    playing.value = false
    return
  }
  audioCtx = uni.createInnerAudioContext()
  audioCtx.src = result.value.tts_audio_url
  audioCtx.onEnded(() => {
    playing.value = false
  })
  audioCtx.onError((err) => {
    playing.value = false
    uni.showToast({ title: '播放失败：' + (err.errMsg ?? '未知'), icon: 'none' })
  })
  audioCtx.play()
  playing.value = true
}

function goBack() {
  uni.navigateBack({ delta: 1 })
}

function goHome() {
  uni.reLaunch({ url: '/pages/index/index' })
}

function goHistory() {
  uni.reLaunch({ url: '/pages/history/history' })
}

onLoad((options) => {
  const taskId = (options?.taskId as string) ?? ''
  if (!taskId) {
    status.value = 'failed'
    errorMsg.value = '缺少 taskId 参数'
    return
  }
  loadResult(taskId)
})
</script>

<style scoped>
.result-page {
  min-height: 100vh;
  padding: 40rpx 32rpx 80rpx;
  background: #f6f8fb;
  box-sizing: border-box;
}

.loading-block,
.failed-block {
  margin-top: 200rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.spinner {
  width: 80rpx;
  height: 80rpx;
  border: 8rpx solid #e0e0e0;
  border-top-color: #4caf50;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 36rpx;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading-text {
  font-size: 32rpx;
  color: #333;
  margin-bottom: 12rpx;
}

.loading-sub {
  font-size: 24rpx;
  color: #999;
}

.failed-icon {
  font-size: 96rpx;
  color: #ff9800;
  margin-bottom: 24rpx;
}

.failed-text {
  font-size: 36rpx;
  color: #1a1a1a;
  margin-bottom: 12rpx;
}

.failed-sub {
  font-size: 26rpx;
  color: #888;
  margin-bottom: 48rpx;
  text-align: center;
}

.retry-btn {
  padding: 20rpx 64rpx;
  background: #4caf50;
  border-radius: 999rpx;
  color: #fff;
  font-size: 28rpx;
}

.hero-card {
  border-radius: 32rpx;
  padding: 60rpx 40rpx;
  color: #fff;
  margin-bottom: 32rpx;
  display: flex;
  flex-direction: column;
}

.hero-card.risk-low {
  background: linear-gradient(135deg, #66bb6a, #2e7d32);
}

.hero-card.risk-medium {
  background: linear-gradient(135deg, #ffa726, #ef6c00);
}

.hero-card.risk-high {
  background: linear-gradient(135deg, #ef5350, #c62828);
}

.risk-tag {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.25);
  padding: 8rpx 24rpx;
  border-radius: 999rpx;
  font-size: 24rpx;
  margin-bottom: 24rpx;
}

.food-name {
  font-size: 44rpx;
  font-weight: 600;
}

.section {
  margin-bottom: 32rpx;
}

.section-title {
  font-size: 28rpx;
  color: #666;
  margin-bottom: 16rpx;
  display: block;
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}

.chip {
  padding: 12rpx 24rpx;
  background: #fff;
  border-radius: 999rpx;
  font-size: 26rpx;
  color: #444;
  border: 1rpx solid #e5e5e5;
}

.advice-card {
  background: #fff;
  border-radius: 24rpx;
  padding: 32rpx;
}

.advice-text {
  font-size: 28rpx;
  color: #333;
  line-height: 1.7;
}

.tts-btn {
  background: #fff;
  border: 2rpx solid #4caf50;
  color: #2e7d32;
  border-radius: 999rpx;
  padding: 24rpx;
  text-align: center;
  font-size: 28rpx;
}

.footer-actions {
  display: flex;
  gap: 24rpx;
  margin-top: 48rpx;
}

.action-btn {
  flex: 1;
  text-align: center;
  padding: 28rpx;
  border-radius: 16rpx;
  background: #fff;
  border: 1rpx solid #e5e5e5;
  font-size: 30rpx;
  color: #444;
}

.action-btn.primary {
  background: #4caf50;
  border-color: #4caf50;
  color: #fff;
  font-weight: 500;
}
</style>

<template>
  <view class="result-page" :style="rootStyle">
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
      <view class="answer-card">
        <view class="answer-header">
          <text class="answer-badge">分析建议</text>
        </view>
        <view class="answer-body">
          <text
            v-for="(line, i) in answerParagraphs"
            :key="`p-${i}`"
            class="answer-paragraph"
          >
            {{ line }}
          </text>
        </view>
      </view>

      <view v-if="result.reference.length > 0" class="reference-section">
        <view class="section-title-row">
          <text class="section-title">参考来源</text>
          <text class="section-count">{{ result.reference.length }} 条</text>
        </view>
        <view
          v-for="(ref, i) in result.reference"
          :key="`ref-${i}`"
          class="reference-card"
        >
          <text class="reference-index">[{{ i + 1 }}]</text>
          <text class="reference-text">{{ ref }}</text>
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
import { computed, ref } from 'vue'
import { pollUntilDone } from '@/api/tasks'
import { useSettings } from '@/store/settings'
import type { AnalysisResult } from '@/types/api'

const { rootStyle } = useSettings()

type Status = 'loading' | 'completed' | 'failed'

const status = ref<Status>('loading')
const result = ref<AnalysisResult | null>(null)
const errorMsg = ref('')

const answerParagraphs = computed(() => {
  if (!result.value) return []
  return result.value.answer.split(/\n+/).filter((s) => s.trim().length > 0)
})

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
  font-size: calc(32rpx * var(--font-scale, 1));
  color: #333;
  margin-bottom: 12rpx;
}

.loading-sub {
  font-size: calc(24rpx * var(--font-scale, 1));
  color: #999;
}

.failed-icon {
  font-size: calc(96rpx * var(--font-scale, 1));
  color: #ff9800;
  margin-bottom: 24rpx;
}

.failed-text {
  font-size: calc(36rpx * var(--font-scale, 1));
  color: #1a1a1a;
  margin-bottom: 12rpx;
}

.failed-sub {
  font-size: calc(26rpx * var(--font-scale, 1));
  color: #888;
  margin-bottom: 48rpx;
  text-align: center;
  padding: 0 40rpx;
  line-height: 1.6;
}

.retry-btn {
  padding: 20rpx 64rpx;
  background: #4caf50;
  border-radius: 999rpx;
  color: #fff;
  font-size: calc(28rpx * var(--font-scale, 1));
}

.answer-card {
  background: #fff;
  border-radius: 24rpx;
  padding: 36rpx;
  margin-bottom: 32rpx;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.04);
}

.answer-header {
  margin-bottom: 24rpx;
}

.answer-badge {
  display: inline-block;
  background: linear-gradient(135deg, #4caf50, #2e7d32);
  color: #fff;
  font-size: calc(24rpx * var(--font-scale, 1));
  padding: 8rpx 24rpx;
  border-radius: 999rpx;
  font-weight: 500;
}

.answer-body {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.answer-paragraph {
  font-size: calc(30rpx * var(--font-scale, 1));
  color: #1a1a1a;
  line-height: 1.7;
}

.reference-section {
  background: #fff;
  border-radius: 24rpx;
  padding: 32rpx;
  margin-bottom: 32rpx;
}

.section-title-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 24rpx;
}

.section-title {
  font-size: calc(28rpx * var(--font-scale, 1));
  font-weight: 600;
  color: #1a1a1a;
}

.section-count {
  font-size: calc(22rpx * var(--font-scale, 1));
  color: #999;
}

.reference-card {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
  padding: 20rpx 0;
  border-top: 1rpx solid #f0f0f0;
}

.reference-card:first-of-type {
  border-top: none;
  padding-top: 0;
}

.reference-index {
  flex-shrink: 0;
  font-size: calc(24rpx * var(--font-scale, 1));
  color: #4caf50;
  font-weight: 600;
  width: 48rpx;
}

.reference-text {
  flex: 1;
  font-size: calc(26rpx * var(--font-scale, 1));
  color: #555;
  line-height: 1.6;
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
  font-size: calc(30rpx * var(--font-scale, 1));
  color: #444;
}

.action-btn.primary {
  background: #4caf50;
  border-color: #4caf50;
  color: #fff;
  font-weight: 500;
}
</style>

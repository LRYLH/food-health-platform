<template>
  <view class="history-page" :style="rootStyle">
    <view class="page-title">
      <text>历史扫描</text>
      <text class="page-subtitle">{{ total }} 条记录</text>
    </view>

    <view v-if="loading && records.length === 0" class="loading-block">
      <view class="spinner" />
    </view>

    <view v-else-if="records.length === 0" class="empty-block">
      <text class="empty-icon">∅</text>
      <text class="empty-text">还没有扫描记录</text>
      <view class="empty-btn" @tap="goHome">
        <text>去扫描第一份</text>
      </view>
    </view>

    <view v-else>
      <view v-for="r in records" :key="r.task_id" class="record-card">
        <view class="record-main">
          <text class="food-name">{{ r.food_name || '未识别食品' }}</text>
          <text class="created-at">{{ formatTime(r.created_at) }}</text>
        </view>
        <view class="risk-badge" :class="`risk-${r.risk_level.toLowerCase()}`">
          <text>{{ riskLabel(r.risk_level) }}</text>
        </view>
      </view>

      <view v-if="hasMore" class="load-more" @tap="loadMore">
        <text>{{ loading ? '加载中...' : '加载更多' }}</text>
      </view>
      <view v-else class="no-more">
        <text>没有更多了</text>
      </view>
    </view>

    <BottomNav current="/pages/history/history" />
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import BottomNav from '@/components/BottomNav.vue'
import { getHistory } from '@/api/history'
import { useSettings } from '@/store/settings'
import type { HistoryRecord, RiskLevel } from '@/types/api'

const { rootStyle } = useSettings()

const PAGE_SIZE = 10

const records = ref<HistoryRecord[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)

const hasMore = computed(() => records.value.length < total.value)

function riskLabel(level: RiskLevel): string {
  return { LOW: '低', MEDIUM: '中', HIGH: '高' }[level]
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadPage(targetPage: number) {
  if (loading.value) return
  loading.value = true
  try {
    const resp = await getHistory({ page: targetPage, size: PAGE_SIZE })
    if (targetPage === 1) {
      records.value = resp.records
    } else {
      records.value = [...records.value, ...resp.records]
    }
    total.value = resp.total
    page.value = targetPage
  } catch (e) {
    uni.showToast({ title: e instanceof Error ? e.message : '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function loadMore() {
  if (!hasMore.value || loading.value) return
  loadPage(page.value + 1)
}

function goHome() {
  uni.reLaunch({ url: '/pages/index/index' })
}

onShow(() => {
  loadPage(1)
})
</script>

<style scoped>
.history-page {
  min-height: 100vh;
  padding: 60rpx 32rpx 160rpx;
  background: #f6f8fb;
  box-sizing: border-box;
}

.page-title {
  display: flex;
  flex-direction: column;
  margin-bottom: 40rpx;
}

.page-title text:first-child {
  font-size: calc(44rpx * var(--font-scale, 1));
  font-weight: 600;
  color: #1a1a1a;
}

.page-subtitle {
  font-size: calc(24rpx * var(--font-scale, 1));
  color: #888;
  margin-top: 8rpx;
}

.loading-block {
  margin-top: 200rpx;
  display: flex;
  justify-content: center;
}

.spinner {
  width: 64rpx;
  height: 64rpx;
  border: 6rpx solid #e0e0e0;
  border-top-color: #4caf50;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.empty-block {
  margin-top: 200rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.empty-icon {
  font-size: calc(96rpx * var(--font-scale, 1));
  color: #ccc;
  margin-bottom: 24rpx;
}

.empty-text {
  font-size: calc(28rpx * var(--font-scale, 1));
  color: #888;
  margin-bottom: 48rpx;
}

.empty-btn {
  padding: 20rpx 64rpx;
  background: #4caf50;
  color: #fff;
  border-radius: 999rpx;
  font-size: calc(28rpx * var(--font-scale, 1));
}

.record-card {
  background: #fff;
  border-radius: 24rpx;
  padding: 28rpx 32rpx;
  margin-bottom: 20rpx;
  display: flex;
  align-items: center;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.03);
}

.record-main {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.food-name {
  font-size: calc(32rpx * var(--font-scale, 1));
  color: #1a1a1a;
  margin-bottom: 8rpx;
}

.created-at {
  font-size: calc(24rpx * var(--font-scale, 1));
  color: #999;
}

.risk-badge {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: calc(28rpx * var(--font-scale, 1));
  font-weight: 600;
}

.risk-badge.risk-low {
  background: #4caf50;
}

.risk-badge.risk-medium {
  background: #ff9800;
}

.risk-badge.risk-high {
  background: #e53935;
}

.load-more,
.no-more {
  text-align: center;
  padding: 32rpx;
  color: #999;
  font-size: calc(26rpx * var(--font-scale, 1));
}
</style>

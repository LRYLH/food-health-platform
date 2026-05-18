<template>
  <view class="home">
    <view class="header">
      <text class="greeting">{{ greeting }}</text>
      <text class="welcome">来扫描一份食品吧</text>
    </view>

    <view class="cta-card" @tap="handleScan">
      <view class="cta-icon">📷</view>
      <text class="cta-title">拍照分析</text>
      <text class="cta-sub">配料表、风险评估、健康建议一键直达</text>
      <view class="cta-button">
        <text class="cta-button-text">{{ scanning ? '处理中...' : '开始扫描' }}</text>
      </view>
    </view>

    <view class="info-grid">
      <view class="info-item" @tap="goHistory">
        <text class="info-num">{{ historyCount }}</text>
        <text class="info-label">历史扫描</text>
      </view>
      <view class="info-item" @tap="goProfile">
        <text class="info-num">{{ profileItemCount }}</text>
        <text class="info-label">健康标签</text>
      </view>
    </view>

    <BottomNav current="/pages/index/index" />
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import BottomNav from '@/components/BottomNav.vue'
import { getHistory } from '@/api/history'
import { getProfile } from '@/api/profile'
import { submitAnalysis } from '@/api/tasks'

const scanning = ref(false)
const historyCount = ref(0)
const profileItemCount = ref(0)

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '凌晨好'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

async function refreshDashboard() {
  try {
    const [h, p] = await Promise.all([getHistory({ page: 1, size: 1 }), getProfile()])
    historyCount.value = h.total
    profileItemCount.value = p.allergens.length + p.chronic_diseases.length
  } catch {
    // ignore dashboard fetch errors silently
  }
}

async function handleScan() {
  if (scanning.value) return
  scanning.value = true
  try {
    const chosen = await uni.chooseImage({ count: 1, sourceType: ['camera', 'album'] })
    const imagePath = chosen.tempFilePaths[0]
    if (!imagePath) return

    const { task_id } = await submitAnalysis({ imagePath })
    uni.navigateTo({ url: `/pages/result/result?taskId=${encodeURIComponent(task_id)}` })
  } catch (e) {
    uni.showToast({
      title: e instanceof Error ? e.message : '提交失败',
      icon: 'none',
    })
  } finally {
    scanning.value = false
  }
}

function goHistory() {
  uni.reLaunch({ url: '/pages/history/history' })
}

function goProfile() {
  uni.reLaunch({ url: '/pages/profile/profile' })
}

onShow(() => {
  refreshDashboard()
})
</script>

<style scoped>
.home {
  min-height: 100vh;
  padding: 60rpx 40rpx 160rpx;
  background: linear-gradient(180deg, #f0f7f4 0%, #ffffff 320rpx);
  box-sizing: border-box;
}

.header {
  display: flex;
  flex-direction: column;
  margin-bottom: 60rpx;
}

.greeting {
  font-size: 32rpx;
  color: #888;
  margin-bottom: 12rpx;
}

.welcome {
  font-size: 48rpx;
  font-weight: 600;
  color: #1a1a1a;
}

.cta-card {
  background: linear-gradient(135deg, #4caf50 0%, #2e7d32 100%);
  border-radius: 32rpx;
  padding: 60rpx 40rpx;
  color: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  box-shadow: 0 16rpx 40rpx rgba(46, 125, 50, 0.25);
  margin-bottom: 48rpx;
}

.cta-icon {
  font-size: 80rpx;
  margin-bottom: 20rpx;
}

.cta-title {
  font-size: 40rpx;
  font-weight: 600;
  margin-bottom: 12rpx;
}

.cta-sub {
  font-size: 24rpx;
  opacity: 0.85;
  text-align: center;
  margin-bottom: 36rpx;
  line-height: 1.6;
}

.cta-button {
  background: rgba(255, 255, 255, 0.2);
  padding: 20rpx 60rpx;
  border-radius: 999rpx;
  border: 2rpx solid rgba(255, 255, 255, 0.5);
}

.cta-button-text {
  font-size: 28rpx;
  color: #fff;
  font-weight: 500;
}

.info-grid {
  display: flex;
  gap: 24rpx;
}

.info-item {
  flex: 1;
  background: #fff;
  border-radius: 24rpx;
  padding: 36rpx 24rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.04);
}

.info-num {
  font-size: 56rpx;
  font-weight: 600;
  color: #2e7d32;
  margin-bottom: 8rpx;
}

.info-label {
  font-size: 24rpx;
  color: #888;
}
</style>

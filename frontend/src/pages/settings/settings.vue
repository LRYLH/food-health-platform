<template>
  <view class="settings-page" :style="rootStyle">
    <view class="page-title">
      <text>设置</text>
    </view>

    <view class="section">
      <view class="section-header">
        <text class="section-title">阅读字号</text>
      </view>
      <text class="section-hint">选择更舒适的字号大小</text>

      <view class="option-grid">
        <view
          class="option-card"
          :class="{ active: !isLargeFont }"
          @tap="setLargeFont(false)"
        >
          <text class="option-label-sm">标准</text>
          <text class="option-preview-sm">食品安全分析</text>
          <text v-if="!isLargeFont" class="option-check">✓</text>
        </view>
        <view
          class="option-card"
          :class="{ active: isLargeFont }"
          @tap="setLargeFont(true)"
        >
          <text class="option-label-lg">大字</text>
          <text class="option-preview-lg">食品安全分析</text>
          <text v-if="isLargeFont" class="option-check">✓</text>
        </view>
      </view>
    </view>

    <view class="footer-note">
      <text>切换后所有页面文字会自动调整大小。</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { useSettings } from '@/store/settings'

const { rootStyle, isLargeFont, setLargeFont } = useSettings()
</script>

<style scoped>
.settings-page {
  min-height: 100vh;
  padding: 60rpx 32rpx 60rpx;
  background: #f6f8fb;
  box-sizing: border-box;
}

.page-title {
  margin-bottom: 48rpx;
}

.page-title text {
  font-size: calc(44rpx * var(--font-scale, 1));
  font-weight: 600;
  color: #1a1a1a;
}

.section {
  background: #fff;
  border-radius: 24rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
}

.section-header {
  margin-bottom: 12rpx;
}

.section-title {
  font-size: calc(32rpx * var(--font-scale, 1));
  font-weight: 600;
  color: #1a1a1a;
}

.section-hint {
  font-size: calc(24rpx * var(--font-scale, 1));
  color: #999;
  margin-bottom: 28rpx;
  display: block;
}

.option-grid {
  display: flex;
  gap: 24rpx;
}

.option-card {
  flex: 1;
  position: relative;
  background: #f6f8fb;
  border: 2rpx solid transparent;
  border-radius: 20rpx;
  padding: 32rpx 24rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16rpx;
}

.option-card.active {
  background: #e8f5e9;
  border-color: #4caf50;
}

.option-check {
  position: absolute;
  top: 12rpx;
  right: 18rpx;
  font-size: 28rpx;
  color: #4caf50;
  font-weight: 600;
}

.option-label-sm,
.option-label-lg {
  color: #888;
  font-weight: 500;
}

.option-label-sm {
  font-size: 26rpx;
}

.option-label-lg {
  font-size: 26rpx;
}

.option-card.active .option-label-sm,
.option-card.active .option-label-lg {
  color: #2e7d32;
}

.option-preview-sm {
  font-size: 28rpx;
  color: #1a1a1a;
}

.option-preview-lg {
  font-size: 42rpx;
  color: #1a1a1a;
  font-weight: 500;
}

.footer-note {
  margin-top: 32rpx;
  padding: 0 16rpx;
}

.footer-note text {
  font-size: calc(22rpx * var(--font-scale, 1));
  color: #999;
  line-height: 1.6;
}
</style>

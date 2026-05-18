<template>
  <view class="bottom-nav">
    <view
      v-for="item in items"
      :key="item.path"
      class="nav-item"
      :class="{ active: current === item.path }"
      @tap="navigate(item.path)"
    >
      <text class="label">{{ item.label }}</text>
      <view class="indicator" />
    </view>
  </view>
</template>

<script setup lang="ts">
interface NavItem {
  label: string
  path: string
}

const props = defineProps<{ current: string }>()

const items: NavItem[] = [
  { label: '首页', path: '/pages/index/index' },
  { label: '历史', path: '/pages/history/history' },
  { label: '我的', path: '/pages/profile/profile' },
]

function navigate(path: string) {
  if (path === props.current) return
  uni.reLaunch({ url: path })
}
</script>

<style scoped>
.bottom-nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  height: 120rpx;
  background: #fff;
  border-top: 1rpx solid #ececec;
  padding-bottom: env(safe-area-inset-bottom);
  z-index: 100;
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding-top: 12rpx;
}

.label {
  font-size: 26rpx;
  color: #888;
}

.indicator {
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
  background: transparent;
  margin-top: 10rpx;
}

.nav-item.active .label {
  color: #2e7d32;
  font-weight: 600;
}

.nav-item.active .indicator {
  background: #2e7d32;
}
</style>

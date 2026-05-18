<template>
  <view class="profile-page">
    <view class="page-title">
      <text>我的健康档案</text>
      <text class="page-subtitle">用于个性化的食品风险判定</text>
    </view>

    <view v-if="loading" class="loading-block">
      <view class="spinner" />
    </view>

    <template v-else>
      <view class="section">
        <view class="section-header">
          <text class="section-title">过敏原</text>
          <text class="section-count">{{ allergens.length }} 项</text>
        </view>
        <view class="chip-list">
          <view v-for="(item, i) in allergens" :key="`a-${i}`" class="chip">
            <text>{{ item }}</text>
            <text class="chip-remove" @tap="removeAllergen(i)">×</text>
          </view>
          <view class="chip add-chip" @tap="openAdd('allergen')">
            <text>+ 添加</text>
          </view>
        </view>
      </view>

      <view class="section">
        <view class="section-header">
          <text class="section-title">慢性病史</text>
          <text class="section-count">{{ chronicDiseases.length }} 项</text>
        </view>
        <view class="chip-list">
          <view v-for="(item, i) in chronicDiseases" :key="`d-${i}`" class="chip">
            <text>{{ item }}</text>
            <text class="chip-remove" @tap="removeDisease(i)">×</text>
          </view>
          <view class="chip add-chip" @tap="openAdd('disease')">
            <text>+ 添加</text>
          </view>
        </view>
      </view>

      <view v-if="addingType" class="add-input-bar">
        <input
          v-model="newItem"
          class="add-input"
          :placeholder="addingType === 'allergen' ? '例如：海鲜、花生' : '例如：高血压、糖尿病'"
          focus
          @confirm="confirmAdd"
        />
        <view class="add-btn" @tap="confirmAdd">
          <text>确定</text>
        </view>
        <view class="cancel-btn" @tap="cancelAdd">
          <text>取消</text>
        </view>
      </view>

      <view class="save-bar">
        <view class="save-btn" :class="{ disabled: !dirty || saving }" @tap="save">
          <text>{{ saving ? '保存中...' : '保存修改' }}</text>
        </view>
      </view>
    </template>

    <BottomNav current="/pages/profile/profile" />
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { ref } from 'vue'
import BottomNav from '@/components/BottomNav.vue'
import { getProfile, updateProfile } from '@/api/profile'

type AddType = 'allergen' | 'disease' | null

const loading = ref(true)
const saving = ref(false)
const dirty = ref(false)

const allergens = ref<string[]>([])
const chronicDiseases = ref<string[]>([])

const addingType = ref<AddType>(null)
const newItem = ref('')

async function load() {
  loading.value = true
  try {
    const p = await getProfile()
    allergens.value = [...p.allergens]
    chronicDiseases.value = [...p.chronic_diseases]
    dirty.value = false
  } catch (e) {
    uni.showToast({ title: e instanceof Error ? e.message : '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function openAdd(type: Exclude<AddType, null>) {
  addingType.value = type
  newItem.value = ''
}

function cancelAdd() {
  addingType.value = null
  newItem.value = ''
}

function confirmAdd() {
  const v = newItem.value.trim()
  if (!v) {
    cancelAdd()
    return
  }
  if (addingType.value === 'allergen') {
    if (!allergens.value.includes(v)) {
      allergens.value.push(v)
      dirty.value = true
    }
  } else if (addingType.value === 'disease') {
    if (!chronicDiseases.value.includes(v)) {
      chronicDiseases.value.push(v)
      dirty.value = true
    }
  }
  cancelAdd()
}

function removeAllergen(i: number) {
  allergens.value.splice(i, 1)
  dirty.value = true
}

function removeDisease(i: number) {
  chronicDiseases.value.splice(i, 1)
  dirty.value = true
}

async function save() {
  if (!dirty.value || saving.value) return
  saving.value = true
  try {
    await updateProfile({
      allergens: allergens.value,
      chronic_diseases: chronicDiseases.value,
    })
    dirty.value = false
    uni.showToast({ title: '已保存', icon: 'success' })
  } catch (e) {
    uni.showToast({ title: e instanceof Error ? e.message : '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

onShow(() => {
  load()
})
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  padding: 60rpx 32rpx 160rpx;
  background: #f6f8fb;
  box-sizing: border-box;
}

.page-title {
  display: flex;
  flex-direction: column;
  margin-bottom: 48rpx;
}

.page-title text:first-child {
  font-size: 44rpx;
  font-weight: 600;
  color: #1a1a1a;
}

.page-subtitle {
  font-size: 24rpx;
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

.section {
  background: #fff;
  border-radius: 24rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 24rpx;
}

.section-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #1a1a1a;
}

.section-count {
  font-size: 24rpx;
  color: #999;
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}

.chip {
  display: flex;
  align-items: center;
  padding: 12rpx 20rpx;
  background: #e8f5e9;
  border-radius: 999rpx;
  font-size: 26rpx;
  color: #2e7d32;
}

.chip-remove {
  margin-left: 12rpx;
  color: #999;
  font-size: 28rpx;
  line-height: 1;
}

.chip.add-chip {
  background: transparent;
  border: 2rpx dashed #4caf50;
  color: #4caf50;
}

.add-input-bar {
  display: flex;
  gap: 12rpx;
  background: #fff;
  border-radius: 24rpx;
  padding: 16rpx;
  margin-bottom: 24rpx;
  align-items: center;
}

.add-input {
  flex: 1;
  height: 72rpx;
  padding: 0 24rpx;
  font-size: 28rpx;
  background: #f6f8fb;
  border-radius: 12rpx;
}

.add-btn,
.cancel-btn {
  padding: 16rpx 28rpx;
  border-radius: 12rpx;
  font-size: 26rpx;
}

.add-btn {
  background: #4caf50;
  color: #fff;
}

.cancel-btn {
  background: #f0f0f0;
  color: #666;
}

.save-bar {
  margin-top: 48rpx;
}

.save-btn {
  background: #4caf50;
  color: #fff;
  text-align: center;
  padding: 28rpx;
  border-radius: 16rpx;
  font-size: 32rpx;
  font-weight: 500;
}

.save-btn.disabled {
  background: #c8e6c9;
}
</style>

import { computed, ref } from 'vue'

const FONT_SCALE_KEY = 'font_scale'

const NORMAL_SCALE = 1
const LARGE_SCALE = 1.5

const fontScale = ref(NORMAL_SCALE)
let hydrated = false

function hydrate(): void {
  if (hydrated) return
  hydrated = true
  try {
    const stored = uni.getStorageSync(FONT_SCALE_KEY)
    if (typeof stored === 'number' && stored > 0) {
      fontScale.value = stored
    }
  } catch {
    // ignore
  }
}

hydrate()

function persist(value: number): void {
  try {
    uni.setStorageSync(FONT_SCALE_KEY, value)
  } catch {
    // ignore
  }
}

export function useSettings() {
  const isLargeFont = computed(() => fontScale.value >= LARGE_SCALE)
  const rootStyle = computed<Record<string, string>>(() => ({
    '--font-scale': String(fontScale.value),
  }))

  function setLargeFont(on: boolean): void {
    fontScale.value = on ? LARGE_SCALE : NORMAL_SCALE
    persist(fontScale.value)
  }

  return {
    fontScale,
    isLargeFont,
    rootStyle,
    setLargeFont,
  }
}

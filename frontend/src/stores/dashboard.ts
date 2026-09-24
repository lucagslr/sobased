/**
 * Dashboard state: my saved views, the one on screen, and its widget data.
 * The layout is saved on the server (it follows the user across devices);
 * only "which view was open last" stays on the device.
 */
import { useDebounceFn } from '@vueuse/core'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  dashboardApi,
  type DashboardSummary,
  type DashboardView,
  type ViewFilters,
  type WidgetLayout,
} from '@/api/dashboard'

const LAST_VIEW_KEY = 'faiblegraine-dashboard-view'

function lastViewId(): number | null {
  try {
    const value = Number(localStorage.getItem(LAST_VIEW_KEY))
    return Number.isInteger(value) && value > 0 ? value : null
  } catch {
    return null
  }
}

export const useDashboardStore = defineStore('dashboard', () => {
  const views = ref<DashboardView[]>([])
  const currentId = ref<number | null>(null)
  const summary = ref<DashboardSummary | null>(null)
  const loading = ref(false)

  const current = computed(() => views.value.find((view) => view.id === currentId.value) ?? null)

  async function loadSummary() {
    if (currentId.value === null) return
    loading.value = true
    try {
      summary.value = await dashboardApi.summary(currentId.value)
    } finally {
      loading.value = false
    }
  }

  /** Loads my views, picks one (last used, else my default), loads its data. */
  async function init() {
    views.value = await dashboardApi.views()
    const remembered = lastViewId()
    const chosen =
      views.value.find((view) => view.id === remembered) ??
      views.value.find((view) => view.is_default) ??
      views.value[0]
    currentId.value = chosen?.id ?? null
    await loadSummary()
  }

  async function select(id: number) {
    currentId.value = id
    summary.value = null
    try {
      localStorage.setItem(LAST_VIEW_KEY, String(id))
    } catch {
      /* private browsing: not remembered */
    }
    await loadSummary()
  }

  function replace(view: DashboardView) {
    views.value = views.value.map((item) => (item.id === view.id ? view : item))
  }

  // Dragging and resizing fire many changes: one request once things settle.
  const pushLayout = useDebounceFn(async (id: number, layout: WidgetLayout[]) => {
    replace(await dashboardApi.updateView(id, { layout }))
  }, 500)

  /** Applies the layout at once on screen, saves it shortly after. */
  function setLayout(layout: WidgetLayout[]) {
    const view = current.value
    if (!view) return
    replace({ ...view, layout })
    pushLayout(view.id, layout)
  }

  async function saveView(
    id: number,
    body: { name: string; filters: ViewFilters; is_default: boolean },
  ) {
    const saved = await dashboardApi.updateView(id, body)
    // Only one default: the server cleared the previous one.
    views.value = views.value.map((item) =>
      item.id === saved.id
        ? saved
        : { ...item, is_default: saved.is_default ? false : item.is_default },
    )
    if (id === currentId.value) await loadSummary()
  }

  async function createView(body: { name: string; filters: ViewFilters; is_default: boolean }) {
    const created = await dashboardApi.createView(body)
    views.value = await dashboardApi.views()
    await select(created.id)
  }

  async function removeView(id: number) {
    await dashboardApi.removeView(id)
    views.value = await dashboardApi.views()
    if (currentId.value === id)
      await select((views.value.find((v) => v.is_default) ?? views.value[0]).id)
  }

  function reset() {
    views.value = []
    currentId.value = null
    summary.value = null
  }

  return {
    views,
    currentId,
    current,
    summary,
    loading,
    init,
    select,
    loadSummary,
    setLayout,
    saveView,
    createView,
    removeView,
    reset,
  }
})

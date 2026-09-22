/**
 * Unread counter of the bell, polled every 60 s while the app is open
 * (SPEC: no WebSocket), and the list when the page asks for it.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { type Notification, notificationsApi } from '@/api/notifications'

const POLL_MS = 60_000

export const useNotificationsStore = defineStore('notifications', () => {
  const unread = ref(0)
  const items = ref<Notification[] | null>(null)
  let timer: ReturnType<typeof setInterval> | null = null

  async function refreshCount() {
    try {
      unread.value = (await notificationsApi.unreadCount()).unread
    } catch {
      /* offline or signed out: the badge keeps its last value */
    }
  }

  function startPolling() {
    if (timer) return
    refreshCount()
    timer = setInterval(() => {
      if (document.visibilityState === 'visible') refreshCount()
    }, POLL_MS)
  }

  function stopPolling() {
    if (timer) clearInterval(timer)
    timer = null
  }

  async function load(unreadOnly = false) {
    items.value = await notificationsApi.list(unreadOnly)
    await refreshCount()
  }

  async function markRead(notification: Notification) {
    if (notification.is_read) return
    const updated = await notificationsApi.markRead(notification.id)
    items.value = (items.value ?? []).map((n) => (n.id === updated.id ? updated : n))
    unread.value = Math.max(0, unread.value - 1)
  }

  async function markAllRead() {
    await notificationsApi.markAllRead()
    items.value = (items.value ?? []).map((n) => ({ ...n, is_read: true }))
    unread.value = 0
  }

  return { unread, items, refreshCount, startPolling, stopPolling, load, markRead, markAllRead }
})

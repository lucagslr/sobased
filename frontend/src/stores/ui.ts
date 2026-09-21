/** Interface state that is not business data: theme and toasts. */
import { defineStore } from 'pinia'
import { ref } from 'vue'

import { applyTheme, isThemeChoice, THEME_STORAGE_KEY, type ThemeChoice } from '@/utils/theme'

export interface Toast {
  id: number
  title: string
  description?: string
  kind: 'info' | 'success' | 'error'
}

let nextToastId = 1

function storedTheme(): ThemeChoice {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY)
    return isThemeChoice(value) ? value : 'system'
  } catch {
    return 'system'
  }
}

export const useUiStore = defineStore('ui', () => {
  const theme = ref<ThemeChoice>(storedTheme())
  const toasts = ref<Toast[]>([])

  /** Applies and remembers the theme on this device (works signed out too). */
  function setTheme(choice: ThemeChoice) {
    theme.value = choice
    try {
      localStorage.setItem(THEME_STORAGE_KEY, choice)
    } catch {
      /* private browsing: the theme just will not persist */
    }
    applyTheme(choice)
  }

  // In "system" mode, follow the OS when it switches (e.g. at sunset).
  window
    .matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', () => applyTheme(theme.value))

  function toast(title: string, kind: Toast['kind'] = 'info', description?: string) {
    toasts.value.push({ id: nextToastId++, title, description, kind })
  }

  function dismissToast(id: number) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  return { theme, setTheme, toasts, toast, dismissToast }
})

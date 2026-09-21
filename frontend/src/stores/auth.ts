/** Who is signed in. The session itself lives in an HttpOnly cookie. */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { authApi, type Me, type RegisterPayload } from '@/api/auth'
import { ApiError } from '@/api/client'
import { isThemeChoice } from '@/utils/theme'

import { useProjectsStore } from './projects'
import { useUiStore } from './ui'
import { useWorkspacesStore } from './workspaces'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<Me | null>(null)
  /** False until the first /api/me/ probe has answered. */
  const ready = ref(false)
  const isAuthenticated = computed(() => user.value !== null)

  function setUser(me: Me | null) {
    if (me?.id !== user.value?.id) {
      // Signing out, or signing in as someone else: forget the cached tree.
      useWorkspacesStore().reset()
      useProjectsStore().reset()
    }
    user.value = me
    // The account's theme wins over the one remembered on this device.
    if (me && isThemeChoice(me.theme)) useUiStore().setTheme(me.theme)
  }

  /** Called once by the router before the first navigation. */
  async function bootstrap() {
    if (ready.value) return
    try {
      setUser((await authApi.session()).user)
    } catch (error) {
      // Server unreachable: stay signed out, the login page will surface the
      // real problem on the next call.
      if (!(error instanceof ApiError)) throw error
      user.value = null
    } finally {
      ready.value = true
    }
  }

  async function login(username: string, password: string) {
    setUser(await authApi.login(username, password))
  }

  async function register(payload: RegisterPayload) {
    setUser(await authApi.register(payload))
  }

  async function logout() {
    try {
      await authApi.logout()
    } finally {
      setUser(null)
    }
  }

  return { user, ready, isAuthenticated, setUser, bootstrap, login, register, logout }
})

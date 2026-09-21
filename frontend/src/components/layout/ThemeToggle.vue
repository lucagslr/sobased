<script setup lang="ts">
/**
 * Light / dark / system. Saved on the device right away, and on the account
 * when someone is signed in (so the choice follows the user everywhere).
 */
import { Monitor, Moon, Sun } from 'lucide-vue-next'
import { computed } from 'vue'

import { authApi } from '@/api/auth'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import type { ThemeChoice } from '@/utils/theme'

defineProps<{ compact?: boolean }>()

const ui = useUiStore()
const auth = useAuthStore()

const options: { value: ThemeChoice; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Clair', icon: Sun },
  { value: 'dark', label: 'Sombre', icon: Moon },
  { value: 'system', label: 'Système', icon: Monitor },
]

const model = computed<ThemeChoice>({
  get: () => ui.theme,
  set: async (choice) => {
    ui.setTheme(choice)
    if (!auth.isAuthenticated) return
    try {
      auth.setUser(await authApi.updateMe({ theme: choice }))
    } catch {
      ui.toast("Le thème n'a pas pu être enregistré sur ton compte.", 'error')
    }
  },
})
</script>

<template>
  <SegmentedControl v-model="model" label="Thème" :options="options" :hide-labels="compact" />
</template>

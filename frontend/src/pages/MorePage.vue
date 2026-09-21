<script setup lang="ts">
/** Mobile "Plus" tab: everything that does not fit in the bottom bar. */
import { ChevronRight, LogOut } from 'lucide-vue-next'
import { RouterLink, useRouter } from 'vue-router'

import AppAvatar from '@/components/ui/AppAvatar.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { NAV_ITEMS } from '@/router/navigation'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const items = NAV_ITEMS.filter((item) => !item.mobile)

async function signOut() {
  await auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <PageHeader title="Plus" />

  <div v-if="auth.user" class="mb-6 flex items-center gap-3">
    <AppAvatar :name="auth.user.display_name" :src="auth.user.avatar_url" :size="44" />
    <div class="min-w-0">
      <p class="truncate font-medium">{{ auth.user.display_name }}</p>
      <p class="truncate text-sm text-muted">@{{ auth.user.username }}</p>
    </div>
  </div>

  <ul class="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
    <li v-for="item in items" :key="item.to">
      <RouterLink :to="item.to" class="flex h-14 items-center gap-3 px-4 hover:bg-surface-2">
        <component :is="item.icon" class="size-5 text-muted" aria-hidden="true" />
        <span class="flex-1 font-medium">{{ item.label }}</span>
        <ChevronRight class="size-4 text-muted" aria-hidden="true" />
      </RouterLink>
    </li>
    <li>
      <button
        type="button"
        class="flex h-14 w-full items-center gap-3 px-4 text-left hover:bg-surface-2"
        @click="signOut"
      >
        <LogOut class="size-5 text-muted" aria-hidden="true" />
        <span class="font-medium">Se déconnecter</span>
      </button>
    </li>
  </ul>
</template>

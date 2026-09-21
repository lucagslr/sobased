<script setup lang="ts">
/** Avatar + name at the bottom of the sidebar, with settings and sign-out. */
import { ChevronsUpDown, LogOut, Settings } from 'lucide-vue-next'
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuRoot,
  DropdownMenuTrigger,
} from 'reka-ui'
import { useRouter } from 'vue-router'

import AppAvatar from '@/components/ui/AppAvatar.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function signOut() {
  await auth.logout()
  router.push({ name: 'login' })
}

const itemClass =
  'flex h-9 cursor-pointer items-center gap-3 rounded-md px-3 text-sm outline-none data-[highlighted]:bg-surface-2'
</script>

<template>
  <DropdownMenuRoot v-if="auth.user">
    <DropdownMenuTrigger
      class="flex w-full items-center gap-3 rounded-lg p-2 text-left transition-colors hover:bg-surface-2"
    >
      <AppAvatar :name="auth.user.display_name" :src="auth.user.avatar_url" :size="32" />
      <span class="min-w-0 flex-1">
        <span class="block truncate text-sm font-medium">{{ auth.user.display_name }}</span>
        <span class="block truncate text-xs text-muted">@{{ auth.user.username }}</span>
      </span>
      <ChevronsUpDown class="size-4 text-muted" aria-hidden="true" />
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent
        side="top"
        align="start"
        :side-offset="8"
        class="z-50 w-56 rounded-xl border border-line bg-surface p-1 shadow-lg"
      >
        <DropdownMenuItem :class="itemClass" @select="router.push('/parametres')">
          <Settings class="size-4 text-muted" aria-hidden="true" /> Paramètres
        </DropdownMenuItem>
        <DropdownMenuItem :class="itemClass" @select="signOut">
          <LogOut class="size-4 text-muted" aria-hidden="true" /> Se déconnecter
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>

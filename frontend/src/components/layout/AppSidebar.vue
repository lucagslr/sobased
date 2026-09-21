<script setup lang="ts">
/**
 * Desktop navigation. The workspace switcher and the project tree are added
 * above / inside this list in phase 2.
 */
import { RouterLink } from 'vue-router'

import { NAV_ITEMS } from '@/router/navigation'

import UserMenu from './UserMenu.vue'
</script>

<template>
  <aside class="flex-col border-r border-line bg-surface">
    <div class="px-6 pt-7 pb-6 text-sm font-semibold tracking-[0.18em]">SOBASED</div>

    <nav class="flex-1 space-y-0.5 overflow-y-auto px-3" aria-label="Navigation principale">
      <RouterLink
        v-for="item in NAV_ITEMS"
        :key="item.to"
        :to="item.to"
        class="flex h-9 items-center gap-3 rounded-lg px-3 text-sm font-medium text-muted transition-colors hover:bg-surface-2 hover:text-fg"
        :active-class="item.to === '/' ? '' : 'bg-surface-2 !text-fg'"
        :exact-active-class="item.to === '/' ? 'bg-surface-2 !text-fg' : ''"
      >
        <component :is="item.icon" class="size-4" aria-hidden="true" />
        {{ item.label }}
      </RouterLink>
    </nav>

    <div class="border-t border-line p-3">
      <UserMenu />
    </div>
  </aside>
</template>

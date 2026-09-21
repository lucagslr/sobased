<script setup lang="ts">
/** Bottom tabs on phones: Dashboard, Calendrier, Tâches, Projets, Plus. */
import { Ellipsis } from 'lucide-vue-next'
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { NAV_ITEMS } from '@/router/navigation'

const route = useRoute()
const tabs = NAV_ITEMS.filter((item) => item.mobile)
const overflow = NAV_ITEMS.filter((item) => !item.mobile)

// "Plus" is highlighted on /plus and on every page it leads to.
const moreActive = computed(
  () => route.path === '/plus' || overflow.some((item) => route.path.startsWith(item.to)),
)

function isActive(to: string) {
  return to === '/' ? route.path === '/' : route.path.startsWith(to)
}
</script>

<template>
  <nav
    class="border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur"
    aria-label="Navigation principale"
  >
    <ul class="mx-auto flex max-w-md">
      <li v-for="tab in tabs" :key="tab.to" class="flex-1">
        <RouterLink
          :to="tab.to"
          class="flex h-14 flex-col items-center justify-center gap-1 text-[11px] font-medium"
          :class="isActive(tab.to) ? 'text-fg' : 'text-muted'"
          :aria-current="isActive(tab.to) ? 'page' : undefined"
        >
          <component :is="tab.icon" class="size-5" aria-hidden="true" />
          {{ tab.shortLabel ?? tab.label }}
        </RouterLink>
      </li>
      <li class="flex-1">
        <RouterLink
          to="/plus"
          class="flex h-14 flex-col items-center justify-center gap-1 text-[11px] font-medium"
          :class="moreActive ? 'text-fg' : 'text-muted'"
          :aria-current="moreActive ? 'page' : undefined"
        >
          <Ellipsis class="size-5" aria-hidden="true" />
          Plus
        </RouterLink>
      </li>
    </ul>
  </nav>
</template>

<script setup lang="ts">
/**
 * Desktop navigation. The workspace switcher and the project tree are added
 * above / inside this list in phase 2.
 */
import { ref } from 'vue'
import { RouterLink } from 'vue-router'

import WorkspaceFormPanel from '@/components/projects/WorkspaceFormPanel.vue'
import { NAV_ITEMS } from '@/router/navigation'
import { useProjectsStore } from '@/stores/projects'

import ProjectTreeNav from './ProjectTreeNav.vue'
import UserMenu from './UserMenu.vue'
import WorkspaceSwitcher from './WorkspaceSwitcher.vue'

const projects = useProjectsStore()
const workspacePanel = ref(false)
</script>

<template>
  <aside class="flex-col border-r border-line bg-surface">
    <div class="px-6 pt-7 pb-5 text-sm font-semibold tracking-[0.18em]">SOBASED</div>
    <div class="px-3 pb-4"><WorkspaceSwitcher @create="workspacePanel = true" /></div>

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

      <!-- The project tree of the selected workspace, under the main links. -->
      <div v-if="projects.tree.length" class="pt-5">
        <p class="px-3 pb-1.5 text-xs font-semibold tracking-wide text-muted uppercase">
          Arborescence
        </p>
        <ProjectTreeNav :nodes="projects.tree" />
      </div>
    </nav>
    <WorkspaceFormPanel v-model:open="workspacePanel" />

    <div class="border-t border-line p-3">
      <UserMenu />
    </div>
  </aside>
</template>

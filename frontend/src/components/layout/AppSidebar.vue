<script setup lang="ts">
/**
 * Desktop navigation. The workspace switcher and the project tree are added
 * above / inside this list in phase 2.
 */
import { X } from 'lucide-vue-next'
import { ref } from 'vue'
import { RouterLink } from 'vue-router'

import WorkspaceFormPanel from '@/components/projects/WorkspaceFormPanel.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import { NAV_ITEMS } from '@/router/navigation'
import { useNotificationsStore } from '@/stores/notifications'
import { useProjectsStore } from '@/stores/projects'
import { useWorkspacesStore } from '@/stores/workspaces'

import ProjectTreeNav from './ProjectTreeNav.vue'
import UserMenu from './UserMenu.vue'
import WorkspaceSwitcher from './WorkspaceSwitcher.vue'

const projects = useProjectsStore()
const workspaces = useWorkspacesStore()
const notifications = useNotificationsStore()
const workspacePanel = ref(false)
</script>

<template>
  <aside class="flex-col border-r border-line bg-surface">
    <div class="px-6 pt-7 pb-5 text-sm font-semibold tracking-[0.18em]">FAIBLEGRAINE</div>
    <div class="px-3 pb-4">
      <WorkspaceSwitcher @create="workspacePanel = true" />
      <!-- A way out of the filter that does not need the menu. -->
      <button
        v-if="workspaces.current"
        type="button"
        class="mt-1.5 flex items-center gap-1 px-1 text-xs text-muted hover:text-fg"
        @click="workspaces.select('all')"
      >
        <X class="size-3" aria-hidden="true" /> Quitter l'espace, voir tous les projets
      </button>
    </div>

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
        <span
          v-if="item.badge && notifications.unread"
          class="ml-auto rounded-full bg-fg px-1.5 text-[11px] font-semibold text-surface"
          :aria-label="`${notifications.unread} non lues`"
        >
          {{ notifications.unread > 99 ? '99+' : notifications.unread }}
        </span>
      </RouterLink>

      <!-- The project tree, one block per workspace (its name is the container). -->
      <div v-if="projects.tree.length" class="space-y-4 pt-5">
        <div v-for="group in projects.groups" :key="group.workspace.id">
          <button
            v-if="group.roots.length"
            type="button"
            class="flex w-full items-center gap-2 px-3 pb-1.5 text-left text-xs font-semibold tracking-wide text-muted uppercase hover:text-fg"
            :title="`Espace ${group.workspace.name} : n'afficher que ses projets`"
            @click="workspaces.select(group.workspace.id)"
          >
            <ColorDot :color="group.workspace.color" />
            <span class="truncate">{{ group.workspace.name }}</span>
          </button>
          <ProjectTreeNav v-if="group.roots.length" :nodes="group.roots" />
        </div>
      </div>
    </nav>
    <WorkspaceFormPanel v-model:open="workspacePanel" />

    <div class="border-t border-line p-3">
      <UserMenu />
    </div>
  </aside>
</template>

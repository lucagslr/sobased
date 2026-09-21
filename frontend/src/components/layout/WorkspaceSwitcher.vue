<script setup lang="ts">
/**
 * Top of the sidebar: which workspace filters the navigation.
 * "Tous les espaces" is a real choice (SPEC §15), and the default.
 */
import { Check, ChevronsUpDown, Layers, Plus, Settings2 } from 'lucide-vue-next'
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuRoot,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from 'reka-ui'
import { useRouter } from 'vue-router'

import ColorDot from '@/components/ui/ColorDot.vue'
import { useWorkspacesStore } from '@/stores/workspaces'

const emit = defineEmits<{ create: [] }>()
const workspaces = useWorkspacesStore()
const router = useRouter()

const itemClass =
  'flex h-9 cursor-pointer items-center gap-2.5 rounded-md px-2.5 text-sm outline-none data-[highlighted]:bg-surface-2'
</script>

<template>
  <DropdownMenuRoot>
    <DropdownMenuTrigger
      class="flex h-10 w-full items-center gap-2.5 rounded-lg border border-line px-3 text-left text-sm font-medium transition-colors hover:bg-surface-2"
      aria-label="Changer d'espace"
    >
      <ColorDot v-if="workspaces.current" :color="workspaces.current.color" />
      <Layers v-else class="size-4 text-muted" aria-hidden="true" />
      <span class="min-w-0 flex-1 truncate">
        {{ workspaces.current?.name ?? 'Tous les espaces' }}
      </span>
      <ChevronsUpDown class="size-4 text-muted" aria-hidden="true" />
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent
        align="start"
        :side-offset="6"
        class="z-50 max-h-[70vh] w-60 overflow-y-auto rounded-xl border border-line bg-surface p-1 shadow-lg"
      >
        <DropdownMenuItem :class="itemClass" @select="workspaces.select('all')">
          <Layers class="size-4 text-muted" aria-hidden="true" />
          <span class="flex-1">Tous les espaces</span>
          <Check v-if="workspaces.selection === 'all'" class="size-4" aria-hidden="true" />
        </DropdownMenuItem>
        <DropdownMenuItem
          v-for="workspace in workspaces.items"
          :key="workspace.id"
          :class="itemClass"
          @select="workspaces.select(workspace.id)"
        >
          <ColorDot :color="workspace.color" />
          <span class="min-w-0 flex-1 truncate">{{ workspace.name }}</span>
          <Check v-if="workspaces.selection === workspace.id" class="size-4" aria-hidden="true" />
        </DropdownMenuItem>
        <DropdownMenuSeparator class="my-1 h-px bg-line" />
        <DropdownMenuItem :class="itemClass" @select="emit('create')">
          <Plus class="size-4 text-muted" aria-hidden="true" /> Nouvel espace
        </DropdownMenuItem>
        <DropdownMenuItem :class="itemClass" @select="router.push('/parametres/espaces')">
          <Settings2 class="size-4 text-muted" aria-hidden="true" /> Gérer les espaces
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>

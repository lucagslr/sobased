<script setup lang="ts">
/**
 * Projects: "Arbre" (the 4-level tree) or "Cartes" (one card per root project
 * with Passé / En cours / À venir columns). The choice is a display
 * preference of this device.
 */
import { FolderTree, Layers, LayoutGrid, ListTree, Plus } from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import type { ProjectNode, Workspace } from '@/api/projects'
import ProjectCardsView from '@/components/projects/ProjectCardsView.vue'
import ProjectFormPanel from '@/components/projects/ProjectFormPanel.vue'
import ProjectTreeRow from '@/components/projects/ProjectTreeRow.vue'
import WorkspaceFormPanel from '@/components/projects/WorkspaceFormPanel.vue'
import WorkspaceGroupHeader from '@/components/projects/WorkspaceGroupHeader.vue'
import TaskPanel from '@/components/tasks/TaskPanel.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useTaskPanel } from '@/composables/useTaskPanel'
import { useProjectsStore } from '@/stores/projects'
import { useWorkspacesStore } from '@/stores/workspaces'
import { countTree } from '@/utils/projects'
import { atLeast } from '@/utils/roles'

type Mode = 'tree' | 'cards'
const MODE_KEY = 'faiblegraine-projects-mode'
const MODES: { value: Mode; label: string; icon: typeof ListTree }[] = [
  { value: 'tree', label: 'Arbre', icon: ListTree },
  { value: 'cards', label: 'Cartes', icon: LayoutGrid },
]

const projects = useProjectsStore()
const workspaces = useWorkspacesStore()
const router = useRouter()
const { taskId, openTask, closeTask } = useTaskPanel()

const mode = ref<Mode>(storedMode())
const projectPanel = ref(false)
const workspacePanel = ref(false)
const parentForNew = ref<ProjectNode | null>(null)
const workspaceForNew = ref<number | null>(null)
const cardsView = ref<InstanceType<typeof ProjectCardsView> | null>(null)

function storedMode(): Mode {
  try {
    return localStorage.getItem(MODE_KEY) === 'cards' ? 'cards' : 'tree'
  } catch {
    return 'tree'
  }
}
watch(mode, (value) => {
  try {
    localStorage.setItem(MODE_KEY, value)
  } catch {
    /* private browsing: not remembered */
  }
})

onMounted(() => {
  if (!projects.loaded) projects.load()
})
watch(() => projects.showArchived, projects.load)

// A root project needs "editor" on the target workspace.
const canCreateRoot = computed(() => {
  const candidates = workspaces.current ? [workspaces.current] : workspaces.joined
  return candidates.some((w) => atLeast(w.my_role, 'editor'))
})

function openCreate(parent: ProjectNode | null) {
  parentForNew.value = parent
  workspaceForNew.value = null
  projectPanel.value = true
}

/** A root project in a given workspace (from its group header). */
function openCreateIn(workspace: Workspace) {
  parentForNew.value = null
  workspaceForNew.value = workspace.id
  projectPanel.value = true
}

const chipClass = 'flex h-8 items-center gap-1.5 rounded-full border px-3 text-sm transition-colors'
function chipTone(active: boolean): string {
  return active ? 'border-fg bg-fg text-surface' : 'border-line text-muted hover:text-fg'
}

const taskPanelOpen = computed({
  get: () => taskId.value !== null,
  set: (value) => !value && closeTask(),
})
</script>

<template>
  <PageHeader
    title="Projets"
    :subtitle="
      workspaces.current
        ? `Espace ${workspaces.current.name}`
        : `Tous les espaces (${workspaces.items.length})`
    "
  >
    <BaseButton v-if="canCreateRoot" @click="openCreate(null)">
      <Plus class="size-4" aria-hidden="true" /> Nouveau projet
    </BaseButton>
  </PageHeader>

  <!-- The workspace filter, on the page itself (the sidebar switcher does the same). -->
  <div
    v-if="workspaces.items.length"
    class="mb-4 flex flex-wrap items-center gap-2"
    role="group"
    aria-label="Filtrer par espace"
  >
    <button
      type="button"
      :class="[chipClass, chipTone(workspaces.selection === 'all')]"
      :aria-pressed="workspaces.selection === 'all'"
      @click="workspaces.select('all')"
    >
      <Layers class="size-3.5" aria-hidden="true" /> Tous les espaces
    </button>
    <button
      v-for="workspace in workspaces.items"
      :key="workspace.id"
      type="button"
      :class="[chipClass, chipTone(workspaces.selection === workspace.id)]"
      :aria-pressed="workspaces.selection === workspace.id"
      @click="workspaces.select(workspace.id)"
    >
      <ColorDot :color="workspace.color" /> {{ workspace.name }}
    </button>
    <BaseButton variant="ghost" size="sm" @click="workspacePanel = true">
      <Plus class="size-4" aria-hidden="true" /> Nouvel espace
    </BaseButton>
  </div>

  <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
    <SegmentedControl v-model="mode" label="Affichage des projets" :options="MODES" />
    <label v-if="mode === 'tree'" class="flex items-center gap-2 text-sm text-muted">
      <input v-model="projects.showArchived" type="checkbox" class="size-4" />
      Afficher les archivés
    </label>
  </div>

  <div v-if="!projects.loaded || !workspaces.loaded" class="space-y-2">
    <SkeletonBlock v-for="n in 5" :key="n" class="h-12 w-full" />
  </div>

  <EmptyState
    v-else-if="!workspaces.items.length"
    :icon="FolderTree"
    title="Étape 1 : crée un espace"
    text="Un espace est le cadre qui regroupe des projets et les personnes qui y travaillent : l'association, l'école, perso… Les projets (un artiste, un album, un cours) viennent ensuite, à l'intérieur d'un espace."
  >
    <BaseButton @click="workspacePanel = true">Créer mon premier espace</BaseButton>
  </EmptyState>

  <ProjectCardsView v-else-if="mode === 'cards'" ref="cardsView" @open-task="openTask" />

  <div v-else class="space-y-8">
    <section v-for="group in projects.groups" :key="group.workspace.id">
      <WorkspaceGroupHeader
        :workspace="group.workspace"
        :count="countTree(group.roots)"
        :filtered="workspaces.selection === group.workspace.id"
        :can-create="atLeast(group.workspace.my_role, 'editor')"
        @create="openCreateIn(group.workspace)"
        @filter="workspaces.select(group.workspace.id)"
        @clear="workspaces.select('all')"
      />
      <ul v-if="group.roots.length" class="border-t border-line">
        <ProjectTreeRow
          v-for="node in group.roots"
          :key="node.id"
          :node="node"
          @add-child="openCreate"
        />
      </ul>
      <p
        v-else
        class="rounded-xl border border-dashed border-line px-4 py-6 text-center text-sm text-muted"
      >
        Aucun projet dans cet espace pour l'instant.
        <button
          v-if="atLeast(group.workspace.my_role, 'editor')"
          type="button"
          class="font-medium text-fg underline"
          @click="openCreateIn(group.workspace)"
        >
          Créer le premier projet
        </button>
      </p>
    </section>
  </div>

  <ProjectFormPanel
    v-model:open="projectPanel"
    :parent="parentForNew"
    :workspace="workspaceForNew"
    @saved="router.push(`/projets/${$event.id}`)"
  />
  <WorkspaceFormPanel v-model:open="workspacePanel" />
  <TaskPanel v-model:open="taskPanelOpen" :task-id="taskId" @changed="cardsView?.reload()" />
</template>

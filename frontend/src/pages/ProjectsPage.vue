<script setup lang="ts">
/**
 * Projects: "Arbre" (the 4-level tree) or "Cartes" (one card per root project
 * with Passé / En cours / À venir columns). The choice is a display
 * preference of this device.
 */
import { FolderTree, LayoutGrid, ListTree, Plus } from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import type { ProjectNode } from '@/api/projects'
import WorkspaceSwitcher from '@/components/layout/WorkspaceSwitcher.vue'
import ProjectCardsView from '@/components/projects/ProjectCardsView.vue'
import ProjectFormPanel from '@/components/projects/ProjectFormPanel.vue'
import ProjectTreeRow from '@/components/projects/ProjectTreeRow.vue'
import WorkspaceFormPanel from '@/components/projects/WorkspaceFormPanel.vue'
import TaskPanel from '@/components/tasks/TaskPanel.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useTaskPanel } from '@/composables/useTaskPanel'
import { useProjectsStore } from '@/stores/projects'
import { useWorkspacesStore } from '@/stores/workspaces'
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
  projectPanel.value = true
}

const taskPanelOpen = computed({
  get: () => taskId.value !== null,
  set: (value) => !value && closeTask(),
})
</script>

<template>
  <PageHeader
    title="Projets"
    :subtitle="workspaces.current ? workspaces.current.name : 'Tous les espaces'"
  >
    <BaseButton v-if="canCreateRoot" @click="openCreate(null)">
      <Plus class="size-4" aria-hidden="true" /> Nouveau projet
    </BaseButton>
  </PageHeader>

  <!-- Below 1024px there is no sidebar: the workspace filter lives here. -->
  <div class="mb-4 lg:hidden">
    <WorkspaceSwitcher @create="workspacePanel = true" />
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
    title="Commence par créer un espace"
    text="Un espace regroupe tes projets et les personnes avec qui tu les partages : 100SATIONS, École, Perso…"
  >
    <BaseButton @click="workspacePanel = true">Créer mon premier espace</BaseButton>
  </EmptyState>

  <ProjectCardsView v-else-if="mode === 'cards'" ref="cardsView" @open-task="openTask" />

  <EmptyState
    v-else-if="!projects.tree.length"
    :icon="FolderTree"
    title="Aucun projet ici"
    text="Crée un projet racine (un artiste, une école, l'admin de l'asso), puis des sous-projets sur 4 niveaux au maximum."
  >
    <BaseButton v-if="canCreateRoot" @click="openCreate(null)">Nouveau projet</BaseButton>
  </EmptyState>

  <ul v-else class="border-t border-line">
    <ProjectTreeRow
      v-for="node in projects.tree"
      :key="node.id"
      :node="node"
      @add-child="openCreate"
    />
  </ul>

  <ProjectFormPanel
    v-model:open="projectPanel"
    :parent="parentForNew"
    @saved="router.push(`/projets/${$event.id}`)"
  />
  <WorkspaceFormPanel v-model:open="workspacePanel" />
  <TaskPanel v-model:open="taskPanelOpen" :task-id="taskId" @changed="cardsView?.reload()" />
</template>

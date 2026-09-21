<script setup lang="ts">
/**
 * Projects, "Arbre" view. The "Cartes" view (one big card per root project
 * with Passé / En cours / À venir columns) arrives in phase 5.
 */
import { FolderTree, Plus } from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import type { ProjectNode } from '@/api/projects'
import WorkspaceSwitcher from '@/components/layout/WorkspaceSwitcher.vue'
import ProjectFormPanel from '@/components/projects/ProjectFormPanel.vue'
import ProjectTreeRow from '@/components/projects/ProjectTreeRow.vue'
import WorkspaceFormPanel from '@/components/projects/WorkspaceFormPanel.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useProjectsStore } from '@/stores/projects'
import { useWorkspacesStore } from '@/stores/workspaces'
import { atLeast } from '@/utils/roles'

const projects = useProjectsStore()
const workspaces = useWorkspacesStore()
const router = useRouter()

const projectPanel = ref(false)
const workspacePanel = ref(false)
const parentForNew = ref<ProjectNode | null>(null)

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
</script>

<template>
  <PageHeader
    title="Projets"
    :subtitle="workspaces.current ? workspaces.current.name : 'Tous les espaces'"
  >
    <label class="mr-2 hidden items-center gap-2 text-sm text-muted sm:flex">
      <input v-model="projects.showArchived" type="checkbox" class="size-4" />
      Afficher les archivés
    </label>
    <BaseButton v-if="canCreateRoot" @click="openCreate(null)">
      <Plus class="size-4" aria-hidden="true" /> Nouveau projet
    </BaseButton>
  </PageHeader>

  <!-- Below 1024px there is no sidebar: the workspace filter lives here. -->
  <div class="mb-5 space-y-3 lg:hidden">
    <WorkspaceSwitcher @create="workspacePanel = true" />
    <label class="flex items-center gap-2 text-sm text-muted sm:hidden">
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
</template>

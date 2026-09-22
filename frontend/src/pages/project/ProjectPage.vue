<script setup lang="ts">
/**
 * Project page: the SAME component at every level of the tree (SPEC §15).
 * Header (breadcrumb, status, dates, colour, tags) + tabs. Tabs are added as
 * phases deliver them: Activité (13) still to come. The Compta tab only
 * exists with can_view_finance.
 * A project seen as a shell gets a minimal page instead.
 */
import { Pencil, Plus } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import { type Project, projectsApi, type ShellProject } from '@/api/projects'
import ProjectFormPanel from '@/components/projects/ProjectFormPanel.vue'
import StatusBadge from '@/components/projects/StatusBadge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useProjectsStore } from '@/stores/projects'
import { useWorkspacesStore } from '@/stores/workspaces'
import { formatDateRange, MAX_DEPTH } from '@/utils/projects'
import { atLeast } from '@/utils/roles'

import ProjectCalendarTab from './ProjectCalendarTab.vue'
import ProjectContactsTab from './ProjectContactsTab.vue'
import ProjectEventsTab from './ProjectEventsTab.vue'
import ProjectFilesTab from './ProjectFilesTab.vue'
import ProjectFinanceTab from './ProjectFinanceTab.vue'
import ProjectLinksTab from './ProjectLinksTab.vue'
import ProjectOverviewTab from './ProjectOverviewTab.vue'
import ProjectSettingsTab from './ProjectSettingsTab.vue'
import ProjectTasksTab from './ProjectTasksTab.vue'
import ShellProjectView from './ShellProjectView.vue'

const route = useRoute()
const router = useRouter()
const projects = useProjectsStore()
const workspaces = useWorkspacesStore()

const project = ref<Project | ShellProject | null>(null)
const notFound = ref(false)
const editPanel = ref(false)
const childPanel = ref(false)

const projectId = computed(() => Number(route.params.id))
const full = computed(() =>
  project.value && !project.value.is_shell ? (project.value as Project) : null,
)
const node = computed(() => projects.byId.get(projectId.value) ?? null)
const canEdit = computed(() => atLeast(full.value?.my_role, 'editor'))

const ALL_TABS = [
  { slug: 'apercu', label: "Vue d'ensemble" },
  { slug: 'taches', label: 'Tâches' },
  { slug: 'calendrier', label: 'Calendrier' },
  { slug: 'rdv', label: 'RDV' },
  { slug: 'fichiers', label: 'Fichiers' },
  { slug: 'compta', label: 'Compta' },
  { slug: 'contacts', label: 'Contacts' },
  { slug: 'liens', label: 'Liens' },
  { slug: 'parametres', label: 'Paramètres' },
]
// Money is only for those with can_view_finance (SPEC §13); share links
// are an editor's business (SPEC §10).
const TABS = computed(() =>
  ALL_TABS.filter(
    (tab) =>
      (tab.slug !== 'compta' || full.value?.can_view_finance) &&
      (tab.slug !== 'liens' || canEdit.value),
  ),
)
const currentTab = computed(() =>
  TABS.value.some((tab) => tab.slug === route.params.tab) ? String(route.params.tab) : 'apercu',
)
const tags = computed(() => {
  if (!full.value) return []
  const all = workspaces.tagsByWorkspace[full.value.workspace] ?? []
  return all.filter((tag) => full.value!.tags?.includes(tag.id))
})

async function load() {
  notFound.value = false
  project.value = null
  try {
    project.value = await projectsApi.get(projectId.value)
    document.title = `${project.value.name} · SOBASED`
    if (!projects.loaded) await projects.load()
    if (!project.value.is_shell) await workspaces.loadTags(project.value.workspace)
  } catch (error) {
    // 404: deleted, or not mine. Both look the same on purpose.
    if (error instanceof ApiError && error.status === 404) notFound.value = true
    else throw error
  }
}
watch(projectId, load, { immediate: true })
</script>

<template>
  <div v-if="notFound" class="py-16 text-center">
    <h1 class="text-xl font-semibold">Projet introuvable</h1>
    <p class="mt-2 text-sm text-muted">Il a été supprimé, ou tu n'y as pas accès.</p>
    <RouterLink to="/projets" class="mt-4 inline-block font-medium underline">
      Retour aux projets
    </RouterLink>
  </div>

  <div v-else-if="!project" class="space-y-4">
    <SkeletonBlock class="h-5 w-48" />
    <SkeletonBlock class="h-9 w-72" />
    <SkeletonBlock class="h-40 w-full" />
  </div>

  <ShellProjectView v-else-if="project.is_shell" :project="project as ShellProject" />

  <template v-else-if="full">
    <nav
      v-if="full.breadcrumb.length"
      class="mb-3 flex flex-wrap items-center gap-1.5 text-sm text-muted"
      aria-label="Fil d'Ariane"
    >
      <template v-for="crumb in full.breadcrumb" :key="crumb.id">
        <RouterLink
          :to="`/projets/${crumb.id}`"
          class="inline-flex items-center gap-1.5 hover:text-fg"
          :class="crumb.is_shell ? 'italic' : ''"
        >
          <ColorDot :color="crumb.color" /> {{ crumb.name }}
        </RouterLink>
        <span aria-hidden="true">/</span>
      </template>
    </nav>

    <header class="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div class="min-w-0">
        <h1 class="flex items-center gap-3 text-2xl font-semibold tracking-tight">
          <ColorDot :color="full.color ?? '#BFDBFE'" size="md" />
          <span class="truncate">{{ full.name }}</span>
        </h1>
        <div class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm text-muted">
          <StatusBadge :status="full.status ?? 'planned'" :overdue="full.end_overdue" />
          <span>{{ full.type_name }}</span>
          <span v-if="full.start_date || full.end_date">
            {{ formatDateRange(full.start_date, full.end_date) }}
          </span>
          <span
            v-for="tag in tags"
            :key="tag.id"
            class="inline-flex h-6 items-center rounded-full border border-black/10 px-2.5 text-xs font-medium text-stone-800"
            :style="{ backgroundColor: tag.color }"
          >
            {{ tag.name }}
          </span>
        </div>
      </div>
      <div v-if="canEdit" class="flex gap-2">
        <BaseButton v-if="full.depth < MAX_DEPTH" variant="secondary" @click="childPanel = true">
          <Plus class="size-4" aria-hidden="true" /> Sous-projet
        </BaseButton>
        <BaseButton variant="secondary" @click="editPanel = true">
          <Pencil class="size-4" aria-hidden="true" /> Modifier
        </BaseButton>
      </div>
    </header>

    <nav
      class="no-scrollbar -mx-4 mb-6 flex gap-1 overflow-x-auto border-b border-line px-4 sm:mx-0 sm:px-0"
    >
      <RouterLink
        v-for="tab in TABS"
        :key="tab.slug"
        :to="`/projets/${full.id}/${tab.slug}`"
        class="-mb-px shrink-0 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors"
        :class="
          tab.slug === currentTab
            ? 'border-fg text-fg'
            : 'border-transparent text-muted hover:text-fg'
        "
        :aria-current="tab.slug === currentTab ? 'page' : undefined"
      >
        {{ tab.label }}
      </RouterLink>
    </nav>

    <ProjectOverviewTab v-if="currentTab === 'apercu'" :project="full" />
    <ProjectTasksTab v-else-if="currentTab === 'taches'" :project="full" />
    <ProjectCalendarTab v-else-if="currentTab === 'calendrier'" :project="full" />
    <ProjectEventsTab v-else-if="currentTab === 'rdv'" :project="full" />
    <ProjectFilesTab v-else-if="currentTab === 'fichiers'" :project="full" />
    <ProjectFinanceTab v-else-if="currentTab === 'compta'" :project="full" />
    <ProjectContactsTab v-else-if="currentTab === 'contacts'" :project="full" />
    <ProjectLinksTab v-else-if="currentTab === 'liens'" :project="full" />
    <ProjectSettingsTab
      v-else
      :project="full"
      :parent-role="node?.parent ? (projects.byId.get(node.parent)?.my_role ?? null) : null"
      @deleted="router.push(full.parent ? `/projets/${full.parent}` : '/projets')"
      @changed="load"
    />

    <ProjectFormPanel v-model:open="editPanel" :project="full" @saved="load" />
    <ProjectFormPanel
      v-model:open="childPanel"
      :parent="node"
      @saved="router.push(`/projets/${$event.id}`)"
    />
  </template>
</template>

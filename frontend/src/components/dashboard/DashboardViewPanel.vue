<script setup lang="ts">
/**
 * Create or edit a saved view ("Perso", "100SATIONS", "École"): a name and a
 * filter on workspaces, projects (sub-projects included), tags, and "only my
 * tasks". An empty filter means "everything I can see".
 */
import { computed, reactive, ref, watch } from 'vue'

import type { DashboardView } from '@/api/dashboard'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSwitch from '@/components/ui/BaseSwitch.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import FormError from '@/components/ui/FormError.vue'
import SidePanel from '@/components/ui/SidePanel.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useDashboardStore } from '@/stores/dashboard'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { useWorkspacesStore } from '@/stores/workspaces'
import { buildTree, type TreeNode } from '@/utils/projects'

/** `view` = edit that view; null = create a new one. */
const props = defineProps<{ view: DashboardView | null }>()
const open = defineModel<boolean>('open', { required: true })

const dashboard = useDashboardStore()
const workspaces = useWorkspacesStore()
const projects = useProjectsStore()
const ui = useUiStore()
const { loading, error, fieldErrors, submit } = useFormSubmit()
const deleteDialog = ref(false)

const form = reactive({
  name: '',
  is_default: false,
  workspaces: [] as number[],
  projects: [] as number[],
  tags: [] as number[],
  only_mine: false,
})

// Projects as an indented list, per workspace. Shells cannot be picked: they
// have no content of their own.
const projectRows = computed(() => {
  const rows: { node: TreeNode; workspace: string }[] = []
  const walk = (nodes: TreeNode[], workspace: string) => {
    for (const node of nodes) {
      rows.push({ node, workspace })
      walk(node.children, workspace)
    }
  }
  for (const workspace of workspaces.items) {
    walk(buildTree(projects.nodes.filter((n) => n.workspace === workspace.id)), workspace.name)
  }
  return rows
})
const tags = computed(() =>
  workspaces.joined.flatMap((workspace) => workspaces.tagsByWorkspace[workspace.id] ?? []),
)

watch(open, async (isOpen) => {
  if (!isOpen) return
  error.value = ''
  fieldErrors.value = {}
  const filters = props.view?.filters
  Object.assign(form, {
    name: props.view?.name ?? '',
    is_default: props.view?.is_default ?? false,
    workspaces: [...(filters?.workspaces ?? [])],
    projects: [...(filters?.projects ?? [])],
    tags: [...(filters?.tags ?? [])],
    only_mine: filters?.only_mine ?? false,
  })
  await Promise.all(workspaces.joined.map((workspace) => workspaces.loadTags(workspace.id)))
})

function toggle(list: number[], id: number): number[] {
  return list.includes(id) ? list.filter((value) => value !== id) : [...list, id]
}

async function save() {
  const body = {
    name: form.name.trim(),
    is_default: form.is_default,
    filters: {
      workspaces: form.workspaces,
      projects: form.projects,
      tags: form.tags,
      only_mine: form.only_mine,
    },
  }
  const ok = await submit(() =>
    props.view ? dashboard.saveView(props.view.id, body) : dashboard.createView(body),
  )
  if (!ok) return
  ui.toast(props.view ? 'Vue enregistrée' : 'Vue créée', 'success')
  open.value = false
}

async function remove() {
  if (!props.view) return
  await dashboard.removeView(props.view.id)
  deleteDialog.value = false
  open.value = false
  ui.toast('Vue supprimée', 'success')
}
</script>

<template>
  <SidePanel
    v-model:open="open"
    :title="view ? 'Modifier la vue' : 'Nouvelle vue'"
    description="Une vue = un filtre + sa propre disposition de widgets."
  >
    <form id="view-form" class="space-y-6" @submit.prevent="save">
      <FormError :message="error" />
      <BaseInput
        v-model="form.name"
        label="Nom"
        placeholder="Perso, 100SATIONS, École…"
        required
        :errors="fieldErrors.name"
      />
      <BaseSwitch
        v-model="form.is_default"
        label="Vue par défaut"
        description="Celle qui s'ouvre sur un nouvel appareil."
      />
      <BaseSwitch
        v-model="form.only_mine"
        label="Seulement mes tâches"
        description="Ne garde que les tâches qui me sont assignées."
      />

      <fieldset v-if="workspaces.joined.length > 1">
        <legend class="mb-2 text-sm font-medium">Espaces</legend>
        <div class="space-y-1.5">
          <label
            v-for="workspace in workspaces.joined"
            :key="workspace.id"
            class="flex items-center gap-2.5 text-sm"
          >
            <input
              type="checkbox"
              class="size-4"
              :checked="form.workspaces.includes(workspace.id)"
              @change="form.workspaces = toggle(form.workspaces, workspace.id)"
            />
            <ColorDot :color="workspace.color" /> {{ workspace.name }}
          </label>
        </div>
      </fieldset>

      <fieldset v-if="projectRows.length">
        <legend class="text-sm font-medium">Projets</legend>
        <p class="mb-2 text-xs text-muted">Cocher un projet inclut tous ses sous-projets.</p>
        <div class="max-h-64 space-y-1.5 overflow-y-auto rounded-lg border border-line p-3">
          <label
            v-for="{ node } in projectRows"
            :key="node.id"
            class="flex items-center gap-2.5 text-sm"
            :class="node.is_shell ? 'text-muted' : ''"
            :style="{ paddingLeft: `${(node.depth - 1) * 1.1}rem` }"
          >
            <input
              type="checkbox"
              class="size-4"
              :disabled="node.is_shell"
              :checked="form.projects.includes(node.id)"
              @change="form.projects = toggle(form.projects, node.id)"
            />
            <ColorDot :color="node.color" /> <span class="truncate">{{ node.name }}</span>
          </label>
        </div>
      </fieldset>

      <fieldset v-if="tags.length">
        <legend class="mb-2 text-sm font-medium">Tags</legend>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="tag in tags"
            :key="tag.id"
            type="button"
            :aria-pressed="form.tags.includes(tag.id)"
            class="inline-flex h-7 items-center rounded-full border px-2.5 text-xs font-medium"
            :class="
              form.tags.includes(tag.id)
                ? 'border-black/10 text-stone-800'
                : 'border-line text-muted hover:text-fg'
            "
            :style="form.tags.includes(tag.id) ? { backgroundColor: tag.color } : {}"
            @click="form.tags = toggle(form.tags, tag.id)"
          >
            {{ tag.name }}
          </button>
        </div>
      </fieldset>
    </form>

    <template #footer>
      <BaseButton
        v-if="view && dashboard.views.length > 1"
        class="mr-auto"
        variant="ghost"
        @click="deleteDialog = true"
      >
        Supprimer
      </BaseButton>
      <BaseButton variant="secondary" @click="open = false">Annuler</BaseButton>
      <BaseButton type="submit" form="view-form" :loading="loading">
        {{ view ? 'Enregistrer' : 'Créer' }}
      </BaseButton>
    </template>
  </SidePanel>

  <ConfirmDialog
    v-model:open="deleteDialog"
    :title="`Supprimer la vue « ${view?.name} » ?`"
    confirm-label="Supprimer"
    danger
    @confirm="remove"
  >
    <p>Son filtre et sa disposition seront perdus. Tes tâches et projets ne sont pas touchés.</p>
  </ConfirmDialog>
</template>

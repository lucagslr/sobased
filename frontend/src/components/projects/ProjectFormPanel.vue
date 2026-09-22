<script setup lang="ts">
/**
 * Create or edit a project, at any of the 4 levels (same form everywhere).
 *
 * - create under a parent: pass `parent`; the workspace comes from it;
 * - create a root project: pass nothing; the workspace is chosen here when the
 *   sidebar is on "Tous les espaces";
 * - edit: pass `project`.
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { integrationsApi } from '@/api/integrations'
import type { Project, ProjectNode, ProjectStatus } from '@/api/projects'
import { projectsApi } from '@/api/projects'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import BaseSwitch from '@/components/ui/BaseSwitch.vue'
import BaseTextarea from '@/components/ui/BaseTextarea.vue'
import ColorPicker from '@/components/ui/ColorPicker.vue'
import FormError from '@/components/ui/FormError.vue'
import SidePanel from '@/components/ui/SidePanel.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { useWorkspacesStore } from '@/stores/workspaces'
import { PASTEL_PALETTE, STATUS_LABELS, STATUS_ORDER } from '@/utils/projects'
import { atLeast } from '@/utils/roles'

import TagPicker from './TagPicker.vue'

const props = defineProps<{ parent?: ProjectNode | null; project?: Project | null }>()
const emit = defineEmits<{ saved: [project: Project] }>()
const open = defineModel<boolean>('open', { required: true })

const workspaces = useWorkspacesStore()
const projects = useProjectsStore()
const ui = useUiStore()
const { loading, error, fieldErrors, submit } = useFormSubmit()

const form = reactive({
  workspace: 0,
  name: '',
  type: '',
  status: 'planned' as ProjectStatus,
  start_date: '',
  end_date: '',
  color: PASTEL_PALETTE[7],
  description: '',
  tags: [] as number[],
})
const ready = ref(false)
// Drive (SPEC §11): the option only shows when the user connected Drive.
const driveConnected = ref(false)
const createDriveFolder = ref(true)
onMounted(async () => {
  try {
    driveConnected.value = (await integrationsApi.state()).google.picker
  } catch {
    driveConnected.value = false
  }
})

// Workspaces where I may create a root project (editor and up).
const writableWorkspaces = computed(() =>
  workspaces.joined.filter((w) => atLeast(w.my_role, 'editor')),
)
const typeOptions = computed(() =>
  (workspaces.typesByWorkspace[form.workspace] ?? []).map((t) => ({
    value: String(t.id),
    label: t.name,
  })),
)
const statusOptions = STATUS_ORDER.map((value) => ({ value, label: STATUS_LABELS[value] }))
const title = computed(() => {
  if (props.project) return 'Modifier le projet'
  return props.parent ? `Nouveau sous-projet de ${props.parent.name}` : 'Nouveau projet'
})

async function prepare() {
  ready.value = false
  error.value = ''
  fieldErrors.value = {}
  const project = props.project
  if (project) {
    Object.assign(form, {
      workspace: project.workspace,
      name: project.name,
      type: String(project.type),
      status: project.status,
      start_date: project.start_date ?? '',
      end_date: project.end_date ?? '',
      color: project.color ?? PASTEL_PALETTE[7],
      description: project.description ?? '',
      tags: [...(project.tags ?? [])],
    })
  } else {
    const selected = workspaces.selection === 'all' ? undefined : workspaces.selection
    Object.assign(form, {
      workspace: props.parent?.workspace ?? selected ?? writableWorkspaces.value[0]?.id ?? 0,
      name: '',
      type: '',
      status: 'planned',
      start_date: '',
      end_date: '',
      // A sub-project starts with the colour of its parent.
      color: props.parent?.color ?? PASTEL_PALETTE[7],
      description: '',
      tags: [],
    })
  }
  if (form.workspace) await workspaces.loadTypes(form.workspace)
  createDriveFolder.value = true
  ready.value = true
}

watch(open, (isOpen) => isOpen && prepare())
watch(
  () => form.workspace,
  async (id) => {
    if (!id || props.project) return
    await workspaces.loadTypes(id)
    form.type = ''
    form.tags = []
  },
)

async function save() {
  const payload = {
    name: form.name.trim(),
    description: form.description,
    status: form.status,
    start_date: form.start_date || null,
    end_date: form.end_date || null,
    color: form.color,
    tags: form.tags,
    ...(form.type ? { type: Number(form.type) } : {}),
  }
  let saved: Project | undefined
  const ok = await submit(async () => {
    saved = props.project
      ? await projectsApi.update(props.project.id, payload)
      : await projectsApi.create({
          ...payload,
          ...(props.parent ? { parent: props.parent.id } : { workspace: form.workspace }),
          ...(driveConnected.value || props.parent
            ? { create_drive_folder: createDriveFolder.value }
            : {}),
        })
    await projects.load()
  })
  if (!ok || !saved) return
  ui.toast(props.project ? 'Projet enregistré' : 'Projet créé', 'success')
  open.value = false
  emit('saved', saved)
}
</script>

<template>
  <SidePanel v-model:open="open" :title="title">
    <form v-if="ready" id="project-form" class="space-y-5" @submit.prevent="save">
      <FormError :message="error || fieldErrors.parent?.[0] || fieldErrors.workspace?.[0]" />
      <BaseSelect
        v-if="!project && !parent && writableWorkspaces.length > 1"
        :model-value="String(form.workspace)"
        label="Espace"
        :options="writableWorkspaces.map((w) => ({ value: String(w.id), label: w.name }))"
        @update:model-value="form.workspace = Number($event)"
      />
      <BaseInput v-model="form.name" label="Nom" required :errors="fieldErrors.name" />
      <div class="grid gap-4 sm:grid-cols-2">
        <BaseSelect
          v-model="form.type"
          label="Type"
          :options="[{ value: '', label: project ? '—' : 'Autre (par défaut)' }, ...typeOptions]"
          :errors="fieldErrors.type"
        />
        <BaseSelect
          v-model="form.status"
          label="Statut"
          :options="statusOptions"
          :errors="fieldErrors.status"
        />
      </div>
      <div class="grid gap-4 sm:grid-cols-2">
        <BaseInput
          v-model="form.start_date"
          label="Début"
          type="date"
          :errors="fieldErrors.start_date"
        />
        <BaseInput v-model="form.end_date" label="Fin" type="date" :errors="fieldErrors.end_date" />
      </div>
      <ColorPicker v-model="form.color" label="Couleur (pastille dans les calendriers)" />
      <TagPicker
        v-if="form.workspace"
        v-model="form.tags"
        :workspace-id="form.workspace"
        can-create
      />
      <BaseTextarea v-model="form.description" label="Description" :rows="4" />
      <BaseSwitch
        v-if="!project && (driveConnected || parent)"
        v-model="createDriveFolder"
        label="Créer un dossier Google Drive"
        :description="
          parent
            ? 'Dans le dossier Drive du projet parent, quand il en a un.'
            : 'Avec les sous-dossiers Contrats, Visuels, Audio, Vidéo, Compta, Documents.'
        "
      />
    </form>
    <template #footer>
      <BaseButton variant="secondary" @click="open = false">Annuler</BaseButton>
      <BaseButton type="submit" form="project-form" :loading="loading">
        {{ project ? 'Enregistrer' : 'Créer' }}
      </BaseButton>
    </template>
  </SidePanel>
</template>

<script setup lang="ts">
/**
 * "Espaces": my workspaces, and for the one that is opened: name and colour,
 * members, project types, bookkeeping categories, then leave / transfer /
 * delete.
 */
import { Plus, Trash2 } from 'lucide-vue-next'
import { computed, reactive, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { type Category, financeApi } from '@/api/finance'
import { type ProjectType, type Workspace, workspacesApi } from '@/api/projects'
import MembersPanel from '@/components/projects/MembersPanel.vue'
import WorkspaceFormPanel from '@/components/projects/WorkspaceFormPanel.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import ColorPicker from '@/components/ui/ColorPicker.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import FormCard from '@/components/ui/FormCard.vue'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { useWorkspacesStore } from '@/stores/workspaces'
import { atLeast, ROLE_LABELS } from '@/utils/roles'

const workspaces = useWorkspacesStore()
const projects = useProjectsStore()
const ui = useUiStore()

const createPanel = ref(false)
const openId = ref<number | null>(null)
const opened = computed(() => workspaces.joined.find((w) => w.id === openId.value) ?? null)
const isAdmin = computed(() => atLeast(opened.value?.my_role, 'admin'))
const isOwner = computed(() => opened.value?.my_role === 'owner')

const general = reactive({ name: '', color: '#CBD5E1' })
const types = ref<ProjectType[]>([])
const newType = ref('')
const categories = ref<Category[]>([])
const newCategory = ref('')
const heir = ref('')
const deleteDialog = ref(false)
const busy = ref(false)

function fail(error: unknown, fallback: string) {
  const message =
    error instanceof ApiError
      ? (Object.values(error.fieldErrors)[0]?.[0] ?? error.message)
      : fallback
  ui.toast(message, 'error')
}

watch(opened, async (workspace) => {
  if (!workspace) return
  Object.assign(general, { name: workspace.name, color: workspace.color ?? '#CBD5E1' })
  types.value = await workspaces.loadTypes(workspace.id, true)
  categories.value = await financeApi.categories(workspace.id)
})

function toggle(workspace: Workspace) {
  openId.value = openId.value === workspace.id ? null : workspace.id
}

async function run(action: () => Promise<unknown>, success: string, fallback: string) {
  busy.value = true
  try {
    await action()
    ui.toast(success, 'success')
  } catch (error) {
    fail(error, fallback)
  } finally {
    busy.value = false
  }
}

const saveGeneral = () =>
  run(
    async () => {
      await workspacesApi.update(opened.value!.id, { ...general })
      await workspaces.load()
    },
    'Espace enregistré',
    "L'enregistrement a échoué.",
  )

const addType = () =>
  run(
    async () => {
      await workspacesApi.createProjectType(opened.value!.id, newType.value.trim())
      newType.value = ''
      types.value = await workspaces.loadTypes(opened.value!.id, true)
    },
    'Type ajouté',
    "Le type n'a pas pu être ajouté.",
  )

const removeType = (type: ProjectType) =>
  run(
    async () => {
      await workspacesApi.removeProjectType(type.id)
      types.value = await workspaces.loadTypes(opened.value!.id, true)
      await projects.load() // projects using it moved to "Autre"
    },
    'Type supprimé',
    'Ce type ne peut pas être supprimé.',
  )

const addCategory = () =>
  run(
    async () => {
      await financeApi.createCategory(opened.value!.id, newCategory.value.trim())
      newCategory.value = ''
      categories.value = await financeApi.categories(opened.value!.id)
    },
    'Catégorie ajoutée',
    "La catégorie n'a pas pu être ajoutée.",
  )

const removeCategory = (category: Category) =>
  run(
    async () => {
      await financeApi.removeCategory(category.id)
      categories.value = await financeApi.categories(opened.value!.id)
    },
    'Catégorie supprimée',
    'Cette catégorie ne peut pas être supprimée.',
  )

const transfer = () =>
  run(
    async () => {
      await workspacesApi.transferOwnership(opened.value!.id, heir.value.trim().replace(/^@/, ''))
      heir.value = ''
      await workspaces.load()
    },
    'Propriété transférée',
    'Le transfert a échoué.',
  )

const leave = () =>
  run(
    async () => {
      await workspacesApi.leave(opened.value!.id)
      openId.value = null
      await Promise.all([workspaces.load(), projects.load()])
    },
    "Tu as quitté l'espace",
    "Impossible de quitter l'espace.",
  )

async function remove() {
  await run(
    async () => {
      await workspacesApi.remove(opened.value!.id)
      openId.value = null
      deleteDialog.value = false
      await Promise.all([workspaces.load(), projects.load()])
    },
    'Espace supprimé',
    'La suppression a échoué.',
  )
}
</script>

<template>
  <FormCard
    title="Mes espaces"
    description="Un espace regroupe des projets et des membres. Un membre de l'espace a accès à tous ses projets."
  >
    <ul v-if="workspaces.joined.length" class="divide-y divide-line rounded-xl border border-line">
      <li v-for="workspace in workspaces.joined" :key="workspace.id">
        <button
          type="button"
          class="flex w-full items-center gap-3 px-3 py-3 text-left hover:bg-surface-2"
          :aria-expanded="openId === workspace.id"
          @click="toggle(workspace)"
        >
          <ColorDot :color="workspace.color ?? '#CBD5E1'" size="md" />
          <span class="min-w-0 flex-1 truncate font-medium">{{ workspace.name }}</span>
          <span class="text-sm text-muted">
            {{ workspace.my_role ? ROLE_LABELS[workspace.my_role] : '' }}
          </span>
        </button>
      </li>
    </ul>
    <p v-else class="text-sm text-muted">Tu n'as encore aucun espace.</p>
    <BaseButton class="mt-4" variant="secondary" @click="createPanel = true">
      <Plus class="size-4" aria-hidden="true" /> Nouvel espace
    </BaseButton>
  </FormCard>

  <template v-if="opened">
    <FormCard v-if="isAdmin" :title="`${opened.name} : général`">
      <form class="space-y-4" @submit.prevent="saveGeneral">
        <BaseInput v-model="general.name" label="Nom" required />
        <ColorPicker v-model="general.color" label="Couleur" />
        <BaseButton type="submit" :loading="busy">Enregistrer</BaseButton>
      </form>
    </FormCard>

    <FormCard :title="`${opened.name} : membres`">
      <MembersPanel
        :scope="{ workspace: opened.id }"
        :my-role="opened.my_role"
        :can-view-finance="isAdmin"
        :can-edit-finance="isAdmin"
        @changed="workspaces.load()"
      />
    </FormCard>

    <FormCard
      v-if="isAdmin"
      :title="`${opened.name} : types de projet`"
      description="Supprimer un type utilisé bascule ses projets sur « Autre »."
    >
      <ul class="mb-4 flex flex-wrap gap-2">
        <li
          v-for="type in types"
          :key="type.id"
          class="inline-flex h-8 items-center gap-1 rounded-full border border-line pr-1 pl-3 text-sm"
        >
          {{ type.name }}
          <button
            type="button"
            class="rounded-full p-1 text-muted hover:text-danger"
            :aria-label="`Supprimer le type ${type.name}`"
            @click="removeType(type)"
          >
            <Trash2 class="size-3.5" aria-hidden="true" />
          </button>
        </li>
      </ul>
      <form class="flex items-end gap-3" @submit.prevent="addType">
        <div class="flex-1"><BaseInput v-model="newType" label="Nouveau type" required /></div>
        <BaseButton type="submit" variant="secondary" :loading="busy">Ajouter</BaseButton>
      </form>
    </FormCard>

    <FormCard
      v-if="isAdmin"
      :title="`${opened.name} : catégories de compta`"
      description="Supprimer une catégorie utilisée bascule ses écritures sur « Autre »."
    >
      <ul class="mb-4 flex flex-wrap gap-2">
        <li
          v-for="category in categories"
          :key="category.id"
          class="inline-flex h-8 items-center gap-1 rounded-full border border-line pr-1 pl-3 text-sm"
        >
          {{ category.name }}
          <button
            type="button"
            class="rounded-full p-1 text-muted hover:text-danger"
            :aria-label="`Supprimer la catégorie ${category.name}`"
            @click="removeCategory(category)"
          >
            <Trash2 class="size-3.5" aria-hidden="true" />
          </button>
        </li>
      </ul>
      <form class="flex items-end gap-3" @submit.prevent="addCategory">
        <div class="flex-1">
          <BaseInput v-model="newCategory" label="Nouvelle catégorie" required />
        </div>
        <BaseButton type="submit" variant="secondary" :loading="busy">Ajouter</BaseButton>
      </form>
    </FormCard>

    <FormCard v-if="isOwner" :title="`${opened.name} : propriété`">
      <form class="flex flex-wrap items-end gap-3" @submit.prevent="transfer">
        <div class="min-w-48 flex-1">
          <BaseInput
            v-model="heir"
            label="Transférer à (membre de l'espace)"
            placeholder="@helder"
            required
          />
        </div>
        <BaseButton type="submit" variant="secondary" :loading="busy">Transférer</BaseButton>
      </form>
      <div class="mt-6 border-t border-line pt-5">
        <BaseButton variant="danger" @click="deleteDialog = true">Supprimer l'espace…</BaseButton>
      </div>
    </FormCard>
    <FormCard v-else :title="`${opened.name} : quitter`">
      <BaseButton variant="secondary" :loading="busy" @click="leave">Quitter cet espace</BaseButton>
    </FormCard>

    <ConfirmDialog
      v-model:open="deleteDialog"
      :title="`Supprimer l'espace « ${opened.name} » ?`"
      confirm-label="Supprimer définitivement"
      :confirm-name="opened.name"
      danger
      :loading="busy"
      @confirm="remove"
    >
      <p>
        Tous les projets de l'espace et leur contenu seront supprimés, pour tous les membres. Cette
        action est irréversible.
      </p>
    </ConfirmDialog>
  </template>

  <WorkspaceFormPanel v-model:open="createPanel" />
</template>

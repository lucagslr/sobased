<script setup lang="ts">
/**
 * Project settings: members and rights, moving the project in the tree, then
 * the Google Drive folder, then the irreversible actions.
 */
import { computed, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { type Project, projectsApi, type Role } from '@/api/projects'
import DriveFolderCard from '@/components/drive/DriveFolderCard.vue'
import MembersPanel from '@/components/projects/MembersPanel.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import FormCard from '@/components/ui/FormCard.vue'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { useWorkspacesStore } from '@/stores/workspaces'
import { moveTargets } from '@/utils/projects'
import { atLeast } from '@/utils/roles'

const props = defineProps<{
  project: Project
  /** My role on the parent project: deleting a sub-project depends on it. */
  parentRole: Role | null
}>()
const emit = defineEmits<{ deleted: []; changed: [] }>()

const projects = useProjectsStore()
const workspaces = useWorkspacesStore()
const ui = useUiStore()

// --- Move (admin of the project + editor of the destination) -----------------
const ROOT = 'root'
const destination = ref('')
const moving = ref(false)
const canMove = computed(() => atLeast(props.project.my_role, 'admin'))
const moveOptions = computed(() => {
  const options = moveTargets(projects.nodes, props.project.id).map((target) => ({
    value: String(target.id),
    label: target.path,
  }))
  const workspaceRole = workspaces.byId.get(props.project.workspace)?.my_role
  if (props.project.parent !== null && atLeast(workspaceRole, 'editor')) {
    options.unshift({ value: ROOT, label: "— À la racine de l'espace —" })
  }
  return [{ value: '', label: 'Choisir une destination…' }, ...options]
})
watch(
  () => props.project.id,
  () => (destination.value = ''),
)

async function move() {
  if (!destination.value) return
  moving.value = true
  try {
    await projectsApi.move(
      props.project.id,
      destination.value === ROOT ? null : Number(destination.value),
    )
    await projects.load()
    destination.value = ''
    ui.toast('Projet déplacé', 'success', 'Ses sous-projets ont suivi.')
    emit('changed')
  } catch (error) {
    const message =
      error instanceof ApiError ? (error.fieldErrors.parent?.[0] ?? error.message) : ''
    ui.toast(message || "Le projet n'a pas été déplacé.", 'error')
  } finally {
    moving.value = false
  }
}

const deleteDialog = ref(false)
const deleting = ref(false)
const heir = ref('')
const transferring = ref(false)

const isRoot = computed(() => props.project.parent === null)
// SPECIFICATIONS §1.3: a sub-project is content of its parent (editor of the
// parent may delete it); a root project is deleted by its owner only.
const canDelete = computed(() =>
  isRoot.value ? props.project.my_role === 'owner' : atLeast(props.parentRole, 'editor'),
)
const descendants = computed(() => {
  const count = (id: number): number =>
    projects.childrenOf(id).reduce((total, child) => total + 1 + count(child.id), 0)
  return count(props.project.id)
})

async function remove() {
  deleting.value = true
  try {
    await projectsApi.remove(props.project.id)
    await projects.load()
    ui.toast('Projet supprimé', 'success')
    emit('deleted')
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'La suppression a échoué.', 'error')
  } finally {
    deleting.value = false
    deleteDialog.value = false
  }
}

async function transfer() {
  transferring.value = true
  try {
    await projectsApi.transferOwnership(props.project.id, heir.value.trim().replace(/^@/, ''))
    ui.toast('Propriété transférée', 'success', 'Tu es maintenant admin de ce projet.')
    heir.value = ''
    await projects.load()
    emit('changed')
  } catch (error) {
    const message =
      error instanceof ApiError ? (error.fieldErrors.username?.[0] ?? error.message) : ''
    ui.toast(message || 'Le transfert a échoué.', 'error')
  } finally {
    transferring.value = false
  }
}
</script>

<template>
  <div class="max-w-3xl space-y-5">
    <FormCard
      title="Membres et droits"
      description="Un accès donné ici vaut aussi pour tous les sous-projets. Les droits hérités se modifient là où ils ont été donnés."
    >
      <MembersPanel
        :scope="{ project: project.id }"
        :my-role="project.my_role"
        :can-view-finance="project.can_view_finance"
        :can-edit-finance="project.can_edit_finance"
        @changed="emit('changed')"
      />
    </FormCard>

    <DriveFolderCard :project="project" @changed="emit('changed')" />

    <FormCard
      v-if="canMove"
      title="Déplacer le projet"
      description="Change le parent du projet, dans le même espace. Ses sous-projets le suivent, sans jamais dépasser 4 niveaux. Les accès hérités de l'ancien parent sont remplacés par ceux du nouveau."
    >
      <form
        v-if="moveOptions.length > 1"
        class="flex flex-wrap items-end gap-3"
        @submit.prevent="move"
      >
        <div class="min-w-48 flex-1">
          <BaseSelect v-model="destination" label="Destination" :options="moveOptions" />
        </div>
        <BaseButton type="submit" variant="secondary" :loading="moving" :disabled="!destination">
          Déplacer
        </BaseButton>
      </form>
      <p v-else class="text-sm text-muted">
        Aucune destination possible : il faut être éditeur du projet d'accueil, et que la branche y
        tienne en 4 niveaux.
      </p>
    </FormCard>

    <FormCard
      v-if="isRoot && project.my_role === 'owner'"
      title="Transférer la propriété"
      description="Le nouveau propriétaire doit déjà être membre direct de ce projet. Tu deviendras admin."
    >
      <form class="flex flex-wrap items-end gap-3" @submit.prevent="transfer">
        <div class="min-w-48 flex-1">
          <BaseInput v-model="heir" label="Nom d'utilisateur" placeholder="@helder" required />
        </div>
        <BaseButton type="submit" variant="secondary" :loading="transferring">
          Transférer
        </BaseButton>
      </form>
    </FormCard>

    <FormCard
      v-if="canDelete"
      title="Supprimer le projet"
      description="Suppression définitive, sans corbeille. Pour le garder sans l'afficher, passe plutôt son statut à « Archivé »."
    >
      <BaseButton variant="danger" @click="deleteDialog = true">Supprimer…</BaseButton>
    </FormCard>

    <ConfirmDialog
      v-model:open="deleteDialog"
      :title="`Supprimer « ${project.name} » ?`"
      confirm-label="Supprimer définitivement"
      :confirm-name="project.name"
      danger
      :loading="deleting"
      @confirm="remove"
    >
      <p>
        Le projet<template v-if="descendants">
          et ses <strong>{{ descendants }}</strong> sous-projet{{
            descendants > 1 ? 's' : ''
          }}</template
        >
        seront supprimés avec tout leur contenu. Cette action est irréversible.
      </p>
    </ConfirmDialog>
  </div>
</template>

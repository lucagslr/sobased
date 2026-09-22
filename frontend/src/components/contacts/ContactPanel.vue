<script setup lang="ts">
/**
 * Create or edit a contact (SPEC §14). Two ways to create one:
 * - in a workspace (`createIn.workspace`): editor of the workspace;
 * - in a project (`createIn.project`): editor of that project, the contact
 *   is linked to it at once, with an optional role ("réalisateur du clip").
 */
import { Trash2 } from 'lucide-vue-next'
import { computed, reactive, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { type Contact, type ContactPayload, contactsApi } from '@/api/contacts'
import TagPicker from '@/components/projects/TagPicker.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import BaseTextarea from '@/components/ui/BaseTextarea.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import FormError from '@/components/ui/FormError.vue'
import SidePanel from '@/components/ui/SidePanel.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useUiStore } from '@/stores/ui'

export interface CreateContactIn {
  workspace: number
  project?: number
}

const props = defineProps<{
  contact?: Contact | null
  createIn?: CreateContactIn | null
  /** Several workspaces to create in: the user picks one in the form. */
  workspaceChoices?: { id: number; name: string }[]
}>()
const emit = defineEmits<{ saved: [contact: Contact]; deleted: [] }>()
const open = defineModel<boolean>('open', { required: true })

const ui = useUiStore()
const { loading, error, fieldErrors, submit } = useFormSubmit()
const deleteDialog = ref(false)

const form = reactive({
  first_name: '',
  last_name: '',
  organization: '',
  job: '',
  email: '',
  phone: '',
  instagram: '',
  website: '',
  notes: '',
  tags: [] as number[],
  role_label: '',
})

const chosenWorkspace = ref('')
const workspaceOptions = computed(() =>
  (props.workspaceChoices ?? []).map((w) => ({ value: String(w.id), label: w.name })),
)
const workspaceId = computed(
  () =>
    props.contact?.workspace ??
    (workspaceOptions.value.length > 1 && chosenWorkspace.value
      ? Number(chosenWorkspace.value)
      : (props.createIn?.workspace ?? null)),
)
const canEdit = computed(() => !props.contact || props.contact.can_edit)

function fill(source: Contact | null | undefined) {
  Object.assign(form, {
    first_name: source?.first_name ?? '',
    last_name: source?.last_name ?? '',
    organization: source?.organization ?? '',
    job: source?.job ?? '',
    email: source?.email ?? '',
    phone: source?.phone ?? '',
    instagram: source?.instagram ?? '',
    website: source?.website ?? '',
    notes: source?.notes ?? '',
    tags: [...(source?.tags ?? [])],
    role_label: '',
  })
}
watch(
  () => [open.value, props.contact] as const,
  ([isOpen]) => {
    if (!isOpen) return
    error.value = ''
    fieldErrors.value = {}
    chosenWorkspace.value = String(props.createIn?.workspace ?? '')
    fill(props.contact)
  },
  { immediate: true },
)

function payload(): ContactPayload {
  return {
    first_name: form.first_name.trim(),
    last_name: form.last_name.trim(),
    organization: form.organization.trim(),
    job: form.job.trim(),
    email: form.email.trim(),
    phone: form.phone.trim(),
    instagram: form.instagram.trim(),
    website: form.website.trim(),
    notes: form.notes,
    tags: form.tags,
  }
}

async function save() {
  let saved: Contact | undefined
  const ok = await submit(async () => {
    if (props.contact) {
      saved = await contactsApi.update(props.contact.id, payload())
    } else if (props.createIn?.project) {
      saved = await contactsApi.create({
        ...payload(),
        project: props.createIn.project,
        role_label: form.role_label.trim(),
      })
    } else {
      saved = await contactsApi.create({ ...payload(), workspace: workspaceId.value! })
    }
  })
  if (!ok || !saved) return
  ui.toast(props.contact ? 'Contact enregistré' : 'Contact créé', 'success')
  open.value = false
  emit('saved', saved)
}

async function remove() {
  deleteDialog.value = false
  if (!props.contact) return
  try {
    await contactsApi.remove(props.contact.id)
    ui.toast('Contact supprimé', 'success')
    open.value = false
    emit('deleted')
  } catch (caught) {
    ui.toast(caught instanceof ApiError ? caught.message : 'La suppression a échoué.', 'error')
  }
}
</script>

<template>
  <SidePanel
    v-model:open="open"
    :title="contact ? contact.display_name : 'Nouveau contact'"
    :description="contact ? [contact.job, contact.organization].filter(Boolean).join(' · ') : ''"
  >
    <form id="contact-form" class="space-y-5" @submit.prevent="save">
      <FormError :message="error" />
      <fieldset :disabled="!canEdit" class="space-y-5">
        <BaseSelect
          v-if="!contact && workspaceOptions.length > 1"
          v-model="chosenWorkspace"
          label="Espace"
          :options="workspaceOptions"
        />
        <div class="grid grid-cols-2 gap-4">
          <BaseInput v-model="form.first_name" label="Prénom" :errors="fieldErrors.first_name" />
          <BaseInput v-model="form.last_name" label="Nom" :errors="fieldErrors.last_name" />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <BaseInput
            v-model="form.organization"
            label="Organisation"
            placeholder="L'Usine, HEG…"
            :errors="fieldErrors.organization"
          />
          <BaseInput
            v-model="form.job"
            label="Métier"
            placeholder="Programmateur, graphiste…"
            :errors="fieldErrors.job"
          />
        </div>
        <BaseInput
          v-if="createIn?.project && !contact"
          v-model="form.role_label"
          label="Rôle dans ce projet"
          placeholder="Réalisateur du clip"
        />
        <div class="grid grid-cols-2 gap-4">
          <BaseInput v-model="form.email" label="E-mail" type="email" :errors="fieldErrors.email" />
          <BaseInput
            v-model="form.phone"
            label="Téléphone"
            type="tel"
            :errors="fieldErrors.phone"
          />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <BaseInput
            v-model="form.instagram"
            label="Instagram"
            placeholder="@compte"
            :errors="fieldErrors.instagram"
          />
          <BaseInput
            v-model="form.website"
            label="Site web"
            type="url"
            placeholder="https://"
            :errors="fieldErrors.website"
          />
        </div>
        <TagPicker v-if="workspaceId && canEdit" v-model="form.tags" :workspace-id="workspaceId" />
        <BaseTextarea v-model="form.notes" label="Notes" :rows="4" />
      </fieldset>

      <p v-if="contact && !canEdit" class="text-sm text-muted">
        Seuls les éditeurs de l'espace (ou la personne qui a créé ce contact) peuvent le modifier.
      </p>
    </form>

    <section v-if="contact?.links.length" class="mt-7">
      <h3 class="mb-2 text-sm font-semibold">Projets</h3>
      <ul class="space-y-1 text-sm">
        <li v-for="link in contact.links" :key="link.id" class="flex items-center gap-2">
          <span
            class="size-2.5 shrink-0 rounded-full"
            :style="{ backgroundColor: link.project_color }"
            aria-hidden="true"
          />
          <RouterLink :to="`/projets/${link.project}/contacts`" class="hover:underline">
            {{ link.project_name }}
          </RouterLink>
          <span v-if="link.role_label" class="text-muted">· {{ link.role_label }}</span>
        </li>
      </ul>
    </section>

    <template v-if="canEdit" #footer>
      <button
        v-if="contact"
        type="button"
        class="mr-auto rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-danger"
        aria-label="Supprimer le contact"
        @click="deleteDialog = true"
      >
        <Trash2 class="size-4" aria-hidden="true" />
      </button>
      <BaseButton variant="secondary" @click="open = false">Fermer</BaseButton>
      <BaseButton type="submit" form="contact-form" :loading="loading">
        {{ contact ? 'Enregistrer' : 'Créer' }}
      </BaseButton>
    </template>
  </SidePanel>

  <ConfirmDialog
    v-model:open="deleteDialog"
    :title="`Supprimer ${contact?.display_name} ?`"
    confirm-label="Supprimer"
    danger
    @confirm="remove"
  >
    <p>Le contact disparaît de l'espace et de tous les projets où il était lié.</p>
  </ConfirmDialog>
</template>

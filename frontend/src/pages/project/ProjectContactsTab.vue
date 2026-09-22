<script setup lang="ts">
/**
 * "Contacts" tab of a project: the outside people linked to it, each with
 * their role here. An editor links an existing contact of the workspace, or
 * creates a new one (linked at once).
 */
import { Contact as ContactIcon, Link2, Plus, Unlink } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { type Contact, contactsApi, type ProjectContact } from '@/api/contacts'
import type { Project } from '@/api/projects'
import ContactCard from '@/components/contacts/ContactCard.vue'
import ContactPanel from '@/components/contacts/ContactPanel.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SidePanel from '@/components/ui/SidePanel.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useUiStore } from '@/stores/ui'
import { useWorkspacesStore } from '@/stores/workspaces'
import { atLeast } from '@/utils/roles'

const props = defineProps<{ project: Project }>()

const ui = useUiStore()
const workspaces = useWorkspacesStore()

const links = ref<ProjectContact[] | null>(null)
const panel = ref(false)
const editing = ref<Contact | null>(null)
const linkPanel = ref(false)
const candidates = ref<Contact[]>([])
const chosen = ref('')
const role = ref('')
const linking = ref(false)

const canEdit = computed(() => atLeast(props.project.my_role, 'editor'))

async function load() {
  links.value = await contactsApi.links(props.project.id)
  workspaces.loadTags(props.project.workspace)
}
watch(() => props.project.id, load, { immediate: true })

async function openLink() {
  chosen.value = ''
  role.value = ''
  const linked = new Set((links.value ?? []).map((link) => link.contact))
  const all = await contactsApi.list({ workspace: props.project.workspace })
  candidates.value = all.filter((contact) => !linked.has(contact.id))
  linkPanel.value = true
}

const candidateOptions = computed(() => [
  { value: '', label: 'Choisir un contact…' },
  ...candidates.value.map((contact) => ({
    value: String(contact.id),
    label: [contact.display_name, contact.organization].filter(Boolean).join(' · '),
  })),
])

async function link() {
  if (!chosen.value) return
  linking.value = true
  try {
    await contactsApi.link(props.project.id, Number(chosen.value), role.value.trim())
    linkPanel.value = false
    ui.toast('Contact lié au projet', 'success')
    await load()
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : "Le contact n'a pas été lié.", 'error')
  } finally {
    linking.value = false
  }
}

async function unlink(item: ProjectContact) {
  try {
    await contactsApi.unlink(item.id)
    await load()
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'Le lien est resté.', 'error')
  }
}

function openEdit(contact: Contact) {
  editing.value = contact
  panel.value = true
}
function openCreate() {
  editing.value = null
  panel.value = true
}
</script>

<template>
  <div v-if="canEdit" class="mb-4 flex flex-wrap gap-2">
    <BaseButton @click="openCreate">
      <Plus class="size-4" aria-hidden="true" /> Nouveau contact
    </BaseButton>
    <BaseButton variant="secondary" @click="openLink">
      <Link2 class="size-4" aria-hidden="true" /> Lier un contact existant
    </BaseButton>
  </div>

  <div v-if="links === null" class="grid gap-3 md:grid-cols-2">
    <SkeletonBlock v-for="n in 4" :key="n" class="h-24" />
  </div>

  <EmptyState
    v-else-if="!links.length"
    :icon="ContactIcon"
    title="Aucun contact lié"
    :text="
      canEdit
        ? 'Le réalisateur du clip, le programmateur de la date, le prof du cours : lie ici les personnes extérieures du projet.'
        : 'Aucune personne extérieure n\'est encore liée à ce projet.'
    "
  />

  <ul v-else class="grid gap-3 md:grid-cols-2">
    <ContactCard
      v-for="item in links"
      :key="item.id"
      :contact="item.contact_detail"
      :role-label="item.role_label"
      @open="openEdit(item.contact_detail)"
    >
      <template v-if="canEdit" #actions>
        <button
          type="button"
          class="self-start rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-fg"
          :aria-label="`Retirer ${item.contact_detail.display_name} du projet`"
          title="Retirer du projet (le contact reste dans l'espace)"
          @click="unlink(item)"
        >
          <Unlink class="size-4" aria-hidden="true" />
        </button>
      </template>
    </ContactCard>
  </ul>

  <ContactPanel
    v-model:open="panel"
    :contact="editing"
    :create-in="{ workspace: project.workspace, project: project.id }"
    @saved="load"
    @deleted="load"
  />

  <SidePanel v-model:open="linkPanel" title="Lier un contact" :description="project.name">
    <form id="link-form" class="space-y-4" @submit.prevent="link">
      <BaseSelect v-model="chosen" label="Contact" :options="candidateOptions" />
      <BaseInput v-model="role" label="Rôle dans ce projet" placeholder="Réalisateur du clip" />
      <p v-if="candidates.length === 0" class="text-sm text-muted">
        Tous les contacts que tu vois sont déjà liés, ou l'espace n'en a pas encore.
      </p>
    </form>
    <template #footer>
      <BaseButton variant="secondary" @click="linkPanel = false">Annuler</BaseButton>
      <BaseButton type="submit" form="link-form" :loading="linking" :disabled="!chosen">
        Lier
      </BaseButton>
    </template>
  </SidePanel>
</template>

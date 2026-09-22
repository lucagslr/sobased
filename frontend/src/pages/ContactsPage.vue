<script setup lang="ts">
/**
 * Contacts (SPEC §15, page 8): the address book of the selected workspace,
 * or of all of them. A member sees the whole book; a guest of a project
 * only the contacts linked to their projects.
 */
import { Contact as ContactIcon, Plus, Search } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

import { type Contact, contactsApi } from '@/api/contacts'
import ContactCard from '@/components/contacts/ContactCard.vue'
import ContactPanel from '@/components/contacts/ContactPanel.vue'
import WorkspaceSwitcher from '@/components/layout/WorkspaceSwitcher.vue'
import WorkspaceFormPanel from '@/components/projects/WorkspaceFormPanel.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useWorkspacesStore } from '@/stores/workspaces'
import { atLeast } from '@/utils/roles'

const workspaces = useWorkspacesStore()

const contacts = ref<Contact[] | null>(null)
const search = ref('')
const panel = ref(false)
const editing = ref<Contact | null>(null)
const workspacePanel = ref(false)

// Creating needs "editor" on the target workspace: the selected one, or
// (with "Tous les espaces") any I may write to, chosen in the form.
const writable = computed(() => {
  const candidates = workspaces.current ? [workspaces.current] : workspaces.joined
  return candidates.filter((w) => atLeast(w.my_role, 'editor'))
})
const targetWorkspace = computed(() => writable.value[0] ?? null)

async function load() {
  contacts.value = await contactsApi.list({
    workspace: workspaces.selection === 'all' ? undefined : workspaces.selection,
  })
  for (const contact of contacts.value) workspaces.loadTags(contact.workspace)
}
watch(() => workspaces.selection, load, { immediate: true })

const shown = computed(() => {
  const needle = search.value.trim().toLowerCase()
  const list = contacts.value ?? []
  if (!needle) return list
  return list.filter((contact) =>
    [contact.display_name, contact.organization, contact.job, contact.email]
      .join(' ')
      .toLowerCase()
      .includes(needle),
  )
})

function openCreate() {
  editing.value = null
  panel.value = true
}
function openEdit(contact: Contact) {
  editing.value = contact
  panel.value = true
}
</script>

<template>
  <PageHeader
    title="Contacts"
    :subtitle="workspaces.current ? workspaces.current.name : 'Tous les espaces'"
  >
    <BaseButton v-if="targetWorkspace" @click="openCreate">
      <Plus class="size-4" aria-hidden="true" /> Nouveau contact
    </BaseButton>
  </PageHeader>

  <!-- Below 1024px there is no sidebar: the workspace filter lives here. -->
  <div class="mb-4 lg:hidden">
    <WorkspaceSwitcher @create="workspacePanel = true" />
  </div>

  <label class="relative mb-5 block max-w-md">
    <Search class="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden="true" />
    <input
      v-model="search"
      type="search"
      placeholder="Chercher un nom, une organisation, un métier…"
      aria-label="Chercher un contact"
      class="h-10 w-full rounded-lg border border-line bg-surface pr-3 pl-9 text-[15px] placeholder:text-muted"
    />
  </label>

  <div v-if="contacts === null" class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
    <SkeletonBlock v-for="n in 6" :key="n" class="h-24" />
  </div>

  <EmptyState
    v-else-if="!contacts.length"
    :icon="ContactIcon"
    title="Aucun contact"
    text="Programmateurs, graphistes, réalisateurs, profs : les personnes extérieures avec qui tu travailles."
  >
    <BaseButton v-if="targetWorkspace" @click="openCreate">Nouveau contact</BaseButton>
  </EmptyState>

  <p v-else-if="!shown.length" class="text-sm text-muted">Aucun contact ne correspond.</p>

  <ul v-else class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
    <ContactCard
      v-for="contact in shown"
      :key="contact.id"
      :contact="contact"
      @open="openEdit(contact)"
    />
  </ul>

  <ContactPanel
    v-model:open="panel"
    :contact="editing"
    :create-in="targetWorkspace ? { workspace: targetWorkspace.id } : null"
    :workspace-choices="writable"
    @saved="load"
    @deleted="load"
  />
  <WorkspaceFormPanel v-model:open="workspacePanel" />
</template>

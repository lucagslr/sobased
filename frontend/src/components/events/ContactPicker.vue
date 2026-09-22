<script setup lang="ts">
/**
 * Picks contacts among those I can see in a workspace (the address book for
 * a member, the linked contacts for a project guest). Contacts already on the
 * event that I cannot see myself stay listed, so that I never drop them by
 * accident.
 */
import { UserRound } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

import { type Contact, contactsApi } from '@/api/contacts'
import type { EventContact } from '@/api/events'

const props = defineProps<{
  workspaceId: number
  /** Contacts already on the event, as the event describes them. */
  current: EventContact[]
  disabled?: boolean
}>()
const model = defineModel<number[]>({ required: true })

const contacts = ref<Contact[]>([])
const search = ref('')

watch(
  () => props.workspaceId,
  async (workspace) => {
    contacts.value = await contactsApi.list({ workspace })
  },
  { immediate: true },
)

interface Option {
  id: number
  label: string
  detail: string
}

const options = computed<Option[]>(() => {
  const byId = new Map<number, Option>()
  for (const contact of contacts.value) {
    byId.set(contact.id, {
      id: contact.id,
      label: contact.display_name,
      detail: [contact.job, contact.organization].filter(Boolean).join(' · '),
    })
  }
  for (const contact of props.current) {
    if (!byId.has(contact.id)) {
      byId.set(contact.id, {
        id: contact.id,
        label: contact.display_name,
        detail: [contact.job, contact.organization].filter(Boolean).join(' · '),
      })
    }
  }
  return [...byId.values()].sort((a, b) => a.label.localeCompare(b.label, 'fr'))
})

const shown = computed(() => {
  const needle = search.value.trim().toLowerCase()
  if (!needle) return options.value
  return options.value.filter(
    (option) =>
      option.label.toLowerCase().includes(needle) || option.detail.toLowerCase().includes(needle),
  )
})

function toggle(id: number) {
  model.value = model.value.includes(id)
    ? model.value.filter((value) => value !== id)
    : [...model.value, id]
}
</script>

<template>
  <div>
    <p class="mb-1.5 text-sm font-medium">Contacts (personnes extérieures)</p>
    <input
      v-if="options.length > 6 && !disabled"
      v-model="search"
      type="search"
      placeholder="Chercher un contact…"
      aria-label="Chercher un contact"
      class="mb-2 h-9 w-full rounded-lg border border-line bg-surface px-3 text-sm placeholder:text-muted"
    />
    <div v-if="shown.length" class="flex flex-wrap gap-1.5">
      <button
        v-for="option in shown"
        :key="option.id"
        type="button"
        :disabled="disabled"
        :aria-pressed="model.includes(option.id)"
        :title="option.detail || undefined"
        class="inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-sm transition-colors disabled:cursor-default"
        :class="
          model.includes(option.id)
            ? 'border-fg bg-surface-2 font-medium'
            : 'border-line text-muted enabled:hover:text-fg'
        "
        @click="toggle(option.id)"
      >
        <UserRound class="size-3.5" aria-hidden="true" />
        {{ option.label }}
      </button>
    </div>
    <p v-else class="text-sm text-muted">
      {{
        search ? 'Aucun contact ne correspond.' : "Aucun contact dans cet espace pour l'instant."
      }}
    </p>
  </div>
</template>

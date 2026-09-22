<script setup lang="ts">
/** One contact in a list: name, job, organisation, ways to reach them. */
import { AtSign, Globe, Instagram, Phone } from 'lucide-vue-next'

import type { Contact } from '@/api/contacts'
import AppAvatar from '@/components/ui/AppAvatar.vue'
import { useWorkspacesStore } from '@/stores/workspaces'

const props = defineProps<{ contact: Contact; roleLabel?: string }>()
const emit = defineEmits<{ open: [] }>()

const workspaces = useWorkspacesStore()

/** "Réalisateur du clip · L'Usine"; a venue named after its organisation
 * is not repeated under its own name. */
function subtitle(contact: Contact): string {
  const organization = contact.organization === contact.display_name ? '' : contact.organization
  return [props.roleLabel || contact.job, organization].filter(Boolean).join(' · ')
}

function tagsOf(contact: Contact) {
  const all = workspaces.tagsByWorkspace[contact.workspace] ?? []
  return all.filter((tag) => contact.tags.includes(tag.id))
}
</script>

<template>
  <li class="flex gap-3 rounded-xl border border-line bg-surface p-3">
    <AppAvatar :name="contact.display_name" :size="40" />
    <div class="min-w-0 flex-1">
      <button
        type="button"
        class="block text-left font-medium hover:underline"
        @click="emit('open')"
      >
        {{ contact.display_name }}
      </button>
      <p class="truncate text-sm text-muted">
        {{ subtitle(contact) }}
      </p>
      <div class="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        <a
          v-if="contact.email"
          :href="`mailto:${contact.email}`"
          class="inline-flex items-center gap-1 hover:text-fg"
        >
          <AtSign class="size-3.5" aria-hidden="true" /> {{ contact.email }}
        </a>
        <a
          v-if="contact.phone"
          :href="`tel:${contact.phone.replace(/\s/g, '')}`"
          class="inline-flex items-center gap-1 hover:text-fg"
        >
          <Phone class="size-3.5" aria-hidden="true" /> {{ contact.phone }}
        </a>
        <a
          v-if="contact.instagram"
          :href="`https://www.instagram.com/${encodeURIComponent(contact.instagram)}/`"
          target="_blank"
          rel="noopener noreferrer nofollow"
          class="inline-flex items-center gap-1 hover:text-fg"
        >
          <Instagram class="size-3.5" aria-hidden="true" /> @{{ contact.instagram }}
        </a>
        <a
          v-if="contact.website"
          :href="contact.website"
          target="_blank"
          rel="noopener noreferrer nofollow"
          class="inline-flex items-center gap-1 hover:text-fg"
        >
          <Globe class="size-3.5" aria-hidden="true" /> Site
        </a>
      </div>
      <div v-if="tagsOf(contact).length" class="mt-2 flex flex-wrap gap-1">
        <span
          v-for="tag in tagsOf(contact)"
          :key="tag.id"
          class="inline-flex h-5 items-center rounded-full border border-black/10 px-2 text-[11px] font-medium text-stone-800"
          :style="{ backgroundColor: tag.color }"
        >
          {{ tag.name }}
        </span>
      </div>
    </div>
    <slot name="actions" />
  </li>
</template>

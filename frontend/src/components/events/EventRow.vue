<script setup lang="ts">
/** One event in an agenda list: date, type, place, who, minutes written or not. */
import { FileText, MapPin, Repeat } from 'lucide-vue-next'
import { computed } from 'vue'

import type { Event } from '@/api/events'
import AppAvatar from '@/components/ui/AppAvatar.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import { EVENT_TYPE_LABELS, isPast } from '@/utils/events'
import { formatPeriod } from '@/utils/tasks'

const props = defineProps<{ event: Event; showProject?: boolean }>()
const emit = defineEmits<{ open: [] }>()

const over = computed(() => isPast(props.event))
const hasMinutes = computed(() => !!props.event.report.trim() || props.event.decisions.length > 0)
const people = computed(() => [
  ...props.event.participants.map((user) => ({
    key: `u-${user.username}`,
    name: user.display_name,
    src: user.avatar_url,
  })),
  ...props.event.contact_details.map((contact) => ({
    key: `c-${contact.id}`,
    name: contact.display_name,
    src: null as string | null,
  })),
])
</script>

<template>
  <li class="border-b border-line">
    <button
      type="button"
      class="group flex w-full items-start gap-3 px-1 py-3 text-left"
      @click="emit('open')"
    >
      <span class="w-28 shrink-0 pt-0.5 text-sm" :class="over ? 'text-muted' : 'font-medium'">
        {{ formatPeriod(event.start, event.end, event.all_day) }}
      </span>
      <span class="min-w-0 flex-1">
        <span class="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span class="font-medium group-hover:underline" :class="over ? 'text-muted' : ''">
            {{ event.title }}
          </span>
          <span
            class="inline-flex h-5 items-center rounded-full border border-line px-2 text-[11px] font-medium text-muted"
          >
            {{ EVENT_TYPE_LABELS[event.type] }}
          </span>
          <Repeat v-if="event.recurrence" class="size-3.5 text-muted" aria-label="RDV récurrent" />
        </span>
        <span class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          <span v-if="showProject" class="inline-flex items-center gap-1.5">
            <ColorDot :color="event.project_color" /> {{ event.project_name }}
          </span>
          <span v-if="event.location" class="inline-flex items-center gap-1">
            <MapPin class="size-3.5" aria-hidden="true" /> {{ event.location }}
          </span>
          <span v-if="hasMinutes" class="inline-flex items-center gap-1">
            <FileText class="size-3.5" aria-hidden="true" /> Compte rendu
          </span>
          <span v-if="event.tasks.length">
            {{ event.tasks.length }} tâche{{ event.tasks.length > 1 ? 's' : '' }}
          </span>
        </span>
      </span>
      <span class="flex shrink-0 -space-x-1.5">
        <AppAvatar
          v-for="person in people.slice(0, 4)"
          :key="person.key"
          :name="person.name"
          :src="person.src"
          :size="24"
          class="ring-2 ring-bg"
        />
      </span>
    </button>
  </li>
</template>

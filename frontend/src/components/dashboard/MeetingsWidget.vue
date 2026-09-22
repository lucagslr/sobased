<script setup lang="ts">
/** Body of the "RDV à venir" widget: the next two weeks of events. */
import type { Event } from '@/api/events'
import EventRow from '@/components/events/EventRow.vue'

defineProps<{ events: Event[]; total: number }>()
const emit = defineEmits<{ open: [event: Event] }>()
</script>

<template>
  <ul>
    <EventRow
      v-for="event in events"
      :key="event.id"
      :event="event"
      show-project
      @open="emit('open', event)"
    />
  </ul>
  <p v-if="total > events.length" class="pt-2 text-center text-xs text-muted">
    et {{ total - events.length }} de plus
  </p>
</template>

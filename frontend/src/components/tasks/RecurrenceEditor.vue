<script setup lang="ts">
/** Recurrence as three simple choices: how often, every how many, until when. */
import { computed } from 'vue'

import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import { describeRrule, buildRrule, type RecurrenceChoice } from '@/utils/tasks'

defineProps<{ disabled?: boolean }>()
const model = defineModel<RecurrenceChoice>({ required: true })

const FREQUENCIES = [
  { value: '', label: 'Jamais' },
  { value: 'DAILY', label: 'Chaque jour' },
  { value: 'WEEKLY', label: 'Chaque semaine' },
  { value: 'MONTHLY', label: 'Chaque mois' },
  { value: 'YEARLY', label: 'Chaque année' },
]
const UNITS = { DAILY: 'jours', WEEKLY: 'semaines', MONTHLY: 'mois', YEARLY: 'ans' }

const interval = computed({
  get: () => String(model.value.interval),
  set: (value) => (model.value = { ...model.value, interval: Math.max(1, Number(value) || 1) }),
})
const summary = computed(() => describeRrule(buildRrule(model.value)))
</script>

<template>
  <fieldset :disabled="disabled" class="space-y-3">
    <BaseSelect
      :model-value="model.frequency"
      label="Répéter"
      :options="FREQUENCIES"
      @update:model-value="model = { ...model, frequency: $event as RecurrenceChoice['frequency'] }"
    />
    <div v-if="model.frequency" class="grid grid-cols-2 gap-3">
      <BaseInput v-model="interval" :label="`Tous les … ${UNITS[model.frequency]}`" type="number" />
      <BaseInput
        :model-value="model.until"
        label="Jusqu'au (optionnel)"
        type="date"
        @update:model-value="model = { ...model, until: $event }"
      />
    </div>
    <p v-if="summary" class="text-sm text-muted">
      {{ summary }}. Les occurrences des 90 prochains jours sont créées à l'avance.
    </p>
  </fieldset>
</template>

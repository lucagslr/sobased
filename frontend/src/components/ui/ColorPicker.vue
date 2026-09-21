<script setup lang="ts">
/** Swatches of the pastel palette (no free colour: the UI stays coherent). */
import { Check } from 'lucide-vue-next'

import { PASTEL_PALETTE } from '@/utils/projects'

defineProps<{ label: string }>()
const model = defineModel<string>({ required: true })
</script>

<template>
  <div>
    <p class="mb-1.5 text-sm font-medium">{{ label }}</p>
    <div role="radiogroup" :aria-label="label" class="flex flex-wrap gap-2">
      <button
        v-for="color in PASTEL_PALETTE"
        :key="color"
        type="button"
        role="radio"
        :aria-checked="model.toUpperCase() === color"
        :aria-label="color"
        class="flex size-8 items-center justify-center rounded-full border border-black/10 transition-transform hover:scale-110"
        :style="{ backgroundColor: color }"
        @click="model = color"
      >
        <Check
          v-if="model.toUpperCase() === color"
          class="size-4 text-stone-800"
          aria-hidden="true"
        />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
/** Accessible on/off switch (reka-ui) with its label and description. */
import { SwitchRoot, SwitchThumb } from 'reka-ui'
import { useId } from 'vue'

defineProps<{ label: string; description?: string; disabled?: boolean }>()
const model = defineModel<boolean>({ required: true })
const id = useId()
</script>

<template>
  <div class="flex items-start justify-between gap-4">
    <div>
      <label :for="id" class="block text-sm font-medium">{{ label }}</label>
      <p v-if="description" class="mt-0.5 text-sm text-muted">{{ description }}</p>
    </div>
    <SwitchRoot
      :id="id"
      v-model="model"
      :disabled="disabled"
      class="relative h-6 w-10 shrink-0 rounded-full bg-line transition-colors data-[state=checked]:bg-accent"
    >
      <SwitchThumb
        class="block size-5 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[18px] dark:data-[state=checked]:bg-stone-900"
      />
    </SwitchRoot>
  </div>
</template>

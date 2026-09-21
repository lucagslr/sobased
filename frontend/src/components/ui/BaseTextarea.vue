<script setup lang="ts">
import { useId } from 'vue'

defineProps<{ label: string; rows?: number; placeholder?: string; errors?: string[] }>()
const model = defineModel<string>({ required: true })
const id = useId()
</script>

<template>
  <div>
    <label :for="id" class="mb-1.5 block text-sm font-medium">{{ label }}</label>
    <textarea
      :id="id"
      v-model="model"
      :rows="rows ?? 4"
      :placeholder="placeholder"
      class="w-full rounded-lg border border-line bg-surface px-3 py-2 text-[15px] placeholder:text-muted"
    />
    <p v-if="errors?.length" class="mt-1.5 text-sm text-danger">{{ errors[0] }}</p>
  </div>
</template>

<script setup lang="ts">
/** Native <select>: best behaviour on mobile, nothing to reinvent. */
import { useId } from 'vue'

defineProps<{
  label: string
  options: { value: string; label: string }[]
  errors?: string[]
}>()

const model = defineModel<string>({ required: true })
const id = useId()
</script>

<template>
  <div>
    <label :for="id" class="mb-1.5 block text-sm font-medium">{{ label }}</label>
    <select
      :id="id"
      v-model="model"
      class="h-10 w-full rounded-lg border border-line bg-surface px-3 text-[15px]"
    >
      <option v-for="option in options" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>
    <p v-if="errors?.length" class="mt-1.5 text-sm text-danger">{{ errors[0] }}</p>
  </div>
</template>

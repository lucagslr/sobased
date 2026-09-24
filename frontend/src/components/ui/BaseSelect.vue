<script setup lang="ts">
/** Native <select>: best behaviour on mobile, nothing to reinvent. */
import { useId } from 'vue'

defineProps<{
  label: string
  options: { value: string; label: string }[]
  /** Optional <optgroup>s, rendered after `options`. */
  groups?: { label: string; options: { value: string; label: string }[] }[]
  errors?: string[]
  disabled?: boolean
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
      :disabled="disabled"
      class="h-10 w-full rounded-lg border border-line bg-surface px-3 text-[15px] disabled:opacity-60"
    >
      <option v-for="option in options" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
      <optgroup v-for="group in groups" :key="group.label" :label="group.label">
        <option v-for="option in group.options" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </optgroup>
    </select>
    <p v-if="errors?.length" class="mt-1.5 text-sm text-danger">{{ errors[0] }}</p>
  </div>
</template>

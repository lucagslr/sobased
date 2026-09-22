<script setup lang="ts">
/** Labelled text input with hint and server-side error display. */
import { useId } from 'vue'

defineProps<{
  label: string
  type?: string
  autocomplete?: string
  /** Phone keyboard hint: "decimal" for amounts, "numeric", "tel"... */
  inputmode?: 'decimal' | 'numeric' | 'tel' | 'email' | 'url' | 'search' | 'text'
  placeholder?: string
  hint?: string
  /** First error is shown; pass the DRF field errors directly. */
  errors?: string[]
  required?: boolean
  disabled?: boolean
}>()

const model = defineModel<string>({ required: true })
const id = useId()
</script>

<template>
  <div>
    <label :for="id" class="mb-1.5 block text-sm font-medium">{{ label }}</label>
    <input
      :id="id"
      v-model="model"
      :type="type ?? 'text'"
      :inputmode="inputmode"
      :autocomplete="autocomplete"
      :placeholder="placeholder"
      :required="required"
      :disabled="disabled"
      :aria-invalid="errors?.length ? 'true' : undefined"
      :aria-describedby="errors?.length ? `${id}-error` : hint ? `${id}-hint` : undefined"
      class="h-10 w-full rounded-lg border bg-surface px-3 text-[15px] placeholder:text-muted disabled:opacity-60"
      :class="errors?.length ? 'border-danger' : 'border-line'"
    />
    <p v-if="errors?.length" :id="`${id}-error`" class="mt-1.5 text-sm text-danger">
      {{ errors[0] }}
    </p>
    <p v-else-if="hint" :id="`${id}-hint`" class="mt-1.5 text-sm text-muted">{{ hint }}</p>
  </div>
</template>

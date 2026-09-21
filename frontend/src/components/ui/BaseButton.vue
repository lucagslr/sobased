<script setup lang="ts">
/** The only button of the app. `loading` disables it and shows a spinner. */
import { LoaderCircle } from 'lucide-vue-next'

withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
    size?: 'sm' | 'md'
    type?: 'button' | 'submit'
    loading?: boolean
    disabled?: boolean
    block?: boolean
  }>(),
  { variant: 'primary', size: 'md', type: 'button' },
)
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    class="inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:opacity-50"
    :class="[
      size === 'sm' ? 'h-8 px-3 text-sm' : 'h-10 px-4 text-sm',
      block && 'w-full',
      {
        primary: 'bg-accent text-accent-fg hover:opacity-90',
        secondary: 'border border-line bg-surface text-fg hover:bg-surface-2',
        ghost: 'text-fg hover:bg-surface-2',
        danger: 'bg-danger text-white hover:opacity-90 dark:text-stone-950',
      }[variant],
    ]"
  >
    <LoaderCircle v-if="loading" class="size-4 animate-spin" aria-hidden="true" />
    <slot />
  </button>
</template>

<script setup lang="ts">
/** General (non-field) error of a form. Renders nothing when empty. */
defineProps<{ message?: string }>()
</script>

<template>
  <p v-if="message" role="alert" class="rounded-lg bg-danger-soft px-3 py-2.5 text-sm text-danger">
    {{ message }}
  </p>
</template>

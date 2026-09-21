<script setup lang="ts">
/**
 * Centered confirmation. With `confirmName`, the user must type that exact
 * name before the button unlocks: used for irreversible deletions.
 */
import {
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogRoot,
  AlertDialogTitle,
} from 'reka-ui'
import { computed, ref, watch } from 'vue'

import BaseButton from './BaseButton.vue'
import BaseInput from './BaseInput.vue'

const props = defineProps<{
  title: string
  confirmLabel: string
  confirmName?: string
  danger?: boolean
  loading?: boolean
}>()
const emit = defineEmits<{ confirm: [] }>()
const open = defineModel<boolean>('open', { required: true })

const typed = ref('')
watch(open, () => (typed.value = ''))
const unlocked = computed(() => !props.confirmName || typed.value.trim() === props.confirmName)
</script>

<template>
  <AlertDialogRoot v-model:open="open">
    <AlertDialogPortal>
      <AlertDialogOverlay class="fixed inset-0 z-50 bg-black/40" />
      <AlertDialogContent
        class="fixed top-1/2 left-1/2 z-50 w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-line bg-surface p-6 shadow-2xl outline-none"
      >
        <AlertDialogTitle class="text-lg font-semibold">{{ title }}</AlertDialogTitle>
        <AlertDialogDescription as="div" class="mt-2 space-y-3 text-sm text-muted">
          <slot />
        </AlertDialogDescription>
        <div v-if="confirmName" class="mt-4">
          <BaseInput
            v-model="typed"
            :label="`Pour confirmer, écris « ${confirmName} »`"
            autocomplete="off"
          />
        </div>
        <div class="mt-6 flex justify-end gap-2">
          <AlertDialogCancel as-child>
            <BaseButton variant="secondary">Annuler</BaseButton>
          </AlertDialogCancel>
          <AlertDialogAction as-child @click.prevent="emit('confirm')">
            <BaseButton
              :variant="danger ? 'danger' : 'primary'"
              :disabled="!unlocked"
              :loading="loading"
            >
              {{ confirmLabel }}
            </BaseButton>
          </AlertDialogAction>
        </div>
      </AlertDialogContent>
    </AlertDialogPortal>
  </AlertDialogRoot>
</template>

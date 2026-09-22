<script setup lang="ts">
/**
 * Editing or deleting one occurrence of a recurring task or event: only this
 * one, or this one and all the following? (Past and finished ones are never
 * touched.)
 */
import {
  DialogContent,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogRoot,
  DialogTitle,
} from 'reka-ui'

import type { RecurrenceScope } from '@/api/tasks'
import BaseButton from '@/components/ui/BaseButton.vue'

withDefaults(defineProps<{ action: 'save' | 'delete'; followingOnly?: boolean; noun?: string }>(), {
  noun: 'Tâche récurrente',
})
const emit = defineEmits<{ choose: [scope: RecurrenceScope] }>()
const open = defineModel<boolean>('open', { required: true })
</script>

<template>
  <DialogRoot v-model:open="open">
    <DialogPortal>
      <DialogOverlay class="fixed inset-0 z-[60] bg-black/40" />
      <DialogContent
        class="fixed top-1/2 left-1/2 z-[60] w-[calc(100vw-2rem)] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-line bg-surface p-6 shadow-2xl outline-none"
      >
        <DialogTitle class="text-lg font-semibold">{{ noun }}</DialogTitle>
        <DialogDescription class="mt-2 text-sm text-muted">
          {{ action === 'save' ? 'Appliquer la modification à :' : 'Supprimer :' }}
        </DialogDescription>
        <div class="mt-5 space-y-2">
          <BaseButton
            v-if="!followingOnly"
            block
            variant="secondary"
            @click="emit('choose', 'this')"
          >
            Cette occurrence seulement
          </BaseButton>
          <BaseButton
            block
            :variant="action === 'delete' ? 'danger' : 'primary'"
            @click="emit('choose', 'following')"
          >
            Celle-ci et toutes les suivantes
          </BaseButton>
          <BaseButton block variant="ghost" @click="open = false">Annuler</BaseButton>
        </div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>

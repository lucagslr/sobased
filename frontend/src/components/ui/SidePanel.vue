<script setup lang="ts">
/**
 * The editing surface of the app (SPEC §15): a panel sliding from the right
 * on desktop, full screen on phones. One at a time, never stacked.
 * Built on reka-ui's Dialog: focus trap, Escape to close, aria attributes.
 */
import { X } from 'lucide-vue-next'
import {
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogRoot,
  DialogTitle,
} from 'reka-ui'

defineProps<{ title: string; description?: string }>()
const open = defineModel<boolean>('open', { required: true })
</script>

<template>
  <DialogRoot v-model:open="open">
    <DialogPortal>
      <DialogOverlay class="fixed inset-0 z-50 bg-black/30 backdrop-blur-[1px]" />
      <DialogContent
        class="fixed inset-0 z-50 flex flex-col bg-surface shadow-2xl outline-none sm:inset-y-0 sm:right-0 sm:left-auto sm:w-[30rem] sm:border-l sm:border-line"
      >
        <header class="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div class="min-w-0">
            <DialogTitle class="truncate text-lg font-semibold">{{ title }}</DialogTitle>
            <!-- Always rendered: screen readers need a description (hidden if none). -->
            <DialogDescription :class="description ? 'mt-0.5 text-sm text-muted' : 'sr-only'">
              {{ description ?? title }}
            </DialogDescription>
          </div>
          <DialogClose
            class="-mr-1 rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-fg"
            aria-label="Fermer"
          >
            <X class="size-5" aria-hidden="true" />
          </DialogClose>
        </header>
        <div class="flex-1 overflow-y-auto px-5 py-5"><slot /></div>
        <footer
          v-if="$slots.footer"
          class="flex justify-end gap-2 border-t border-line px-5 py-4 pb-[max(1rem,env(safe-area-inset-bottom))]"
        >
          <slot name="footer" />
        </footer>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>

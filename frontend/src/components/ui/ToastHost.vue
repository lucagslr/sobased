<script setup lang="ts">
/** Renders the toasts queued in the ui store (reka-ui handles a11y and timers). */
import { X } from 'lucide-vue-next'
import {
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastRoot,
  ToastTitle,
  ToastViewport,
} from 'reka-ui'

import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
</script>

<template>
  <ToastProvider :duration="4500" swipe-direction="right">
    <ToastRoot
      v-for="toast in ui.toasts"
      :key="toast.id"
      class="flex items-start gap-3 rounded-xl border bg-surface p-4 shadow-lg"
      :class="toast.kind === 'error' ? 'border-danger' : 'border-line'"
      @update:open="(open: boolean) => !open && ui.dismissToast(toast.id)"
    >
      <div class="min-w-0 flex-1">
        <ToastTitle class="text-sm font-medium">{{ toast.title }}</ToastTitle>
        <ToastDescription v-if="toast.description" class="mt-0.5 text-sm text-muted">
          {{ toast.description }}
        </ToastDescription>
      </div>
      <ToastClose class="rounded-md p-1 text-muted hover:text-fg" aria-label="Fermer">
        <X class="size-4" aria-hidden="true" />
      </ToastClose>
    </ToastRoot>
    <!-- Above the mobile tab bar; bottom-right on desktop. -->
    <ToastViewport
      class="fixed inset-x-4 bottom-24 z-50 flex flex-col gap-2 lg:inset-x-auto lg:right-6 lg:bottom-6 lg:w-96"
    />
  </ToastProvider>
</template>

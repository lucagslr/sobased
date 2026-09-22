<script setup lang="ts">
/**
 * Image viewer with area annotations (SPEC §9): existing rectangles are
 * drawn from percentages, so they stay right at any display size; dragging
 * on the image draws a new one, which becomes the anchor of the next
 * comment. Pointer events work the same with a mouse and a finger.
 */
import { computed, ref } from 'vue'

import type { AssetVersion } from '@/api/files'
import type { Thread } from '@/utils/files'
import { commentRect, type Rect, rectFromDrag } from '@/utils/files'

const props = defineProps<{
  version: AssetVersion
  threads: Thread[]
  selectedId: number | null
  /** The rectangle being prepared for a new comment. */
  draft: Rect | null
  canDraw: boolean
}>()
const emit = defineEmits<{ select: [id: number]; draw: [rect: Rect | null] }>()

const box = ref<HTMLElement | null>(null)
const start = ref<{ x: number; y: number } | null>(null)
const current = ref<Rect | null>(null)

const anchored = computed(() =>
  props.threads
    .map((thread) => ({ thread, rect: commentRect(thread.root) }))
    .filter((item): item is { thread: Thread; rect: Rect } => item.rect !== null),
)

function point(event: PointerEvent) {
  const bounds = box.value!.getBoundingClientRect()
  return { x: event.clientX - bounds.left, y: event.clientY - bounds.top }
}

function onDown(event: PointerEvent) {
  if (!props.canDraw || event.button !== 0) return
  event.preventDefault()
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
  start.value = point(event)
  current.value = null
}

function onMove(event: PointerEvent) {
  if (!start.value || !box.value) return
  const bounds = box.value.getBoundingClientRect()
  current.value = rectFromDrag(start.value, point(event), bounds.width, bounds.height)
}

function onUp() {
  if (!start.value) return
  // A plain click clears the draft (and selects nothing).
  emit('draw', current.value)
  start.value = null
  current.value = null
}

function style(rect: Rect) {
  return { left: `${rect.x}%`, top: `${rect.y}%`, width: `${rect.w}%`, height: `${rect.h}%` }
}
</script>

<template>
  <div class="flex justify-center overflow-hidden rounded-xl bg-surface-2 p-2">
    <div
      ref="box"
      class="relative inline-block max-w-full select-none"
      :class="canDraw ? 'cursor-crosshair' : ''"
      :style="{ touchAction: canDraw ? 'none' : 'auto' }"
      @pointerdown="onDown"
      @pointermove="onMove"
      @pointerup="onUp"
      @pointercancel="onUp"
    >
      <img
        :src="version.file_url ?? ''"
        :alt="version.original_filename"
        class="block max-h-[70vh] max-w-full"
        draggable="false"
      />
      <button
        v-for="({ thread, rect }, index) in anchored"
        :key="thread.root.id"
        type="button"
        class="absolute rounded-sm border-2 transition-colors"
        :class="[
          thread.root.id === selectedId
            ? 'z-10 border-warning bg-warning/20'
            : thread.root.is_resolved
              ? 'border-white/50 bg-transparent'
              : 'border-white bg-white/10 shadow-[0_0_0_1px_rgba(0,0,0,.35)]',
        ]"
        :style="style(rect)"
        :aria-label="`Annotation ${index + 1} : ${thread.root.body.slice(0, 60)}`"
        @pointerdown.stop
        @click.stop="emit('select', thread.root.id)"
      >
        <span
          class="absolute -top-2.5 -left-2.5 flex size-5 items-center justify-center rounded-full bg-fg text-[11px] font-semibold text-surface"
        >
          {{ index + 1 }}
        </span>
      </button>
      <div
        v-if="current ?? draft"
        class="pointer-events-none absolute border-2 border-dashed border-warning bg-warning/20"
        :style="style((current ?? draft)!)"
      />
    </div>
  </div>
</template>

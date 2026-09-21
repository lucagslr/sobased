<script setup lang="ts">
/**
 * The box around every dashboard widget: title, counter, scrolling body, and
 * while customising, the controls to move, resize and hide it (decision D3:
 * preset sizes, no free-form grid library).
 */
import { Eye, EyeOff, GripVertical, Minus, MoveVertical, Plus } from 'lucide-vue-next'
import { computed } from 'vue'

import type { WidgetLayout } from '@/api/dashboard'
import { LOCKED_WIDGET, MAX_SIZE, MIN_SIZE, WIDGETS } from '@/utils/dashboard'

const props = defineProps<{
  item: WidgetLayout
  count: number
  editing: boolean
  /** "En retard" with something in it: the only red element of the page. */
  alert?: boolean
}>()
const emit = defineEmits<{ change: [patch: Partial<Omit<WidgetLayout, 'key'>>] }>()

const meta = computed(() => WIDGETS[props.item.key])
const locked = computed(() => props.item.key === LOCKED_WIDGET)
const controlClass =
  'flex size-7 items-center justify-center rounded-md text-muted hover:bg-surface-2 hover:text-fg disabled:opacity-30'
</script>

<template>
  <section
    class="flex flex-col rounded-2xl border bg-surface"
    :class="[
      alert ? 'border-danger' : 'border-line',
      item.hidden ? 'opacity-50' : '',
      item.tall ? 'h-[34rem]' : 'h-80',
    ]"
    :aria-label="meta.title"
  >
    <header class="flex items-center gap-2 px-4 pt-3.5 pb-2">
      <button
        v-if="editing && !locked"
        type="button"
        class="drag-handle -ml-1.5 cursor-grab rounded-md p-1 text-muted hover:bg-surface-2 active:cursor-grabbing"
        :aria-label="`Déplacer le widget ${meta.title}`"
      >
        <GripVertical class="size-4" aria-hidden="true" />
      </button>
      <component
        :is="meta.icon"
        class="size-4 shrink-0"
        :class="alert ? 'text-danger' : 'text-muted'"
        aria-hidden="true"
      />
      <h2 class="min-w-0 flex-1 truncate text-sm font-semibold" :class="alert ? 'text-danger' : ''">
        {{ meta.title }}
      </h2>
      <span
        v-if="!editing"
        class="rounded-full px-2 text-xs font-semibold"
        :class="alert ? 'bg-danger text-white dark:text-stone-950' : 'bg-surface-2 text-muted'"
      >
        {{ count }}
      </span>

      <template v-else>
        <button
          type="button"
          :class="controlClass"
          :disabled="item.size <= MIN_SIZE"
          aria-label="Réduire la largeur"
          @click="emit('change', { size: item.size - 1 })"
        >
          <Minus class="size-3.5" aria-hidden="true" />
        </button>
        <button
          type="button"
          :class="controlClass"
          :disabled="item.size >= MAX_SIZE"
          aria-label="Augmenter la largeur"
          @click="emit('change', { size: item.size + 1 })"
        >
          <Plus class="size-3.5" aria-hidden="true" />
        </button>
        <button
          type="button"
          :class="[controlClass, item.tall ? '!text-fg' : '']"
          :aria-pressed="item.tall"
          aria-label="Hauteur double"
          @click="emit('change', { tall: !item.tall })"
        >
          <MoveVertical class="size-3.5" aria-hidden="true" />
        </button>
        <button
          v-if="!locked"
          type="button"
          :class="controlClass"
          :aria-pressed="item.hidden"
          :aria-label="item.hidden ? 'Afficher ce widget' : 'Masquer ce widget'"
          @click="emit('change', { hidden: !item.hidden })"
        >
          <component :is="item.hidden ? EyeOff : Eye" class="size-3.5" aria-hidden="true" />
        </button>
      </template>
    </header>

    <div class="min-h-0 flex-1 overflow-y-auto px-4 pb-3">
      <p v-if="count === 0" class="pt-6 text-center text-sm text-muted">{{ meta.empty }}</p>
      <slot v-else />
    </div>
  </section>
</template>

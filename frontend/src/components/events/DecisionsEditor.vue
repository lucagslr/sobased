<script setup lang="ts">
/**
 * The ordered list of decisions of a meeting (SPECIFICATIONS §4): one line
 * per decision, added with Enter, removed with its cross. Blank lines are
 * dropped by the server.
 */
import { Plus, X } from 'lucide-vue-next'
import { ref } from 'vue'

import BaseButton from '@/components/ui/BaseButton.vue'

defineProps<{ disabled?: boolean }>()
const model = defineModel<string[]>({ required: true })

const draft = ref('')

function add() {
  const text = draft.value.trim()
  if (!text) return
  model.value = [...model.value, text]
  draft.value = ''
}

function removeAt(index: number) {
  model.value = model.value.filter((_, i) => i !== index)
}
</script>

<template>
  <div>
    <p class="mb-1.5 text-sm font-medium">Décisions</p>
    <ol v-if="model.length" class="mb-2 space-y-1.5">
      <li
        v-for="(decision, index) in model"
        :key="index"
        class="flex items-start gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm"
      >
        <span class="w-5 shrink-0 font-semibold text-muted">{{ index + 1 }}.</span>
        <span class="min-w-0 flex-1 break-words">{{ decision }}</span>
        <button
          v-if="!disabled"
          type="button"
          class="-mr-1 shrink-0 rounded p-0.5 text-muted hover:text-danger"
          :aria-label="`Retirer la décision ${index + 1}`"
          @click="removeAt(index)"
        >
          <X class="size-4" aria-hidden="true" />
        </button>
      </li>
    </ol>
    <p v-else-if="disabled" class="text-sm text-muted">Aucune décision notée.</p>
    <div v-if="!disabled" class="flex gap-2">
      <input
        v-model="draft"
        type="text"
        maxlength="500"
        placeholder="Nouvelle décision…"
        aria-label="Nouvelle décision"
        class="h-9 min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 text-sm placeholder:text-muted"
        @keydown.enter.prevent="add"
      />
      <BaseButton variant="secondary" :disabled="!draft.trim()" @click="add">
        <Plus class="size-4" aria-hidden="true" />
        <span class="sr-only">Ajouter la décision</span>
      </BaseButton>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * « Qui doit quoi à qui » (SPEC §13): open advances per person, then per
 * root project, with « Marquer remboursé » for one project or the whole
 * balance. The server only settles what I may edit.
 */
import { HandCoins } from 'lucide-vue-next'
import { ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { type Advance, financeApi } from '@/api/finance'
import BaseButton from '@/components/ui/BaseButton.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useUiStore } from '@/stores/ui'
import { chf } from '@/utils/money'

const props = defineProps<{ workspaceId?: number; projectId?: number }>()
const emit = defineEmits<{ changed: [] }>()

const ui = useUiStore()
const advances = ref<Advance[] | null>(null)
const busy = ref<string | null>(null)

async function load() {
  advances.value = await financeApi.advances({
    workspace: props.workspaceId,
    project: props.projectId,
  })
}
watch(() => [props.workspaceId, props.projectId], load, { immediate: true })

async function settle(key: string, transactions: number[]) {
  busy.value = key
  try {
    const result = await financeApi.settleAdvances(transactions)
    ui.toast(
      result.updated
        ? `${result.updated} avance${result.updated > 1 ? 's' : ''} marquée${result.updated > 1 ? 's' : ''} remboursée${result.updated > 1 ? 's' : ''}`
        : "Rien n'a été modifié (droits insuffisants ?).",
      result.updated ? 'success' : 'error',
    )
    await load()
    emit('changed')
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : "L'opération a échoué.", 'error')
  } finally {
    busy.value = null
  }
}
</script>

<template>
  <div v-if="advances === null" class="space-y-3">
    <SkeletonBlock v-for="n in 2" :key="n" class="h-24" />
  </div>

  <EmptyState
    v-else-if="!advances.length"
    :icon="HandCoins"
    title="Personne n'attend de remboursement"
    text="Une dépense « Payée par » quelqu'un et « À rembourser » apparaît ici jusqu'à son remboursement."
  />

  <ul v-else class="space-y-3">
    <li
      v-for="person in advances"
      :key="`${person.payer_type}-${person.payer_id}-${person.payer_name}`"
      class="rounded-2xl border border-line p-4"
    >
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="font-semibold">
          {{ person.payer_name }}
          <span class="ml-2 text-sm font-normal text-muted">
            {{ person.payer_type === 'contact' ? 'contact' : '' }}
          </span>
        </h3>
        <div class="flex items-center gap-3">
          <span class="font-semibold tabular-nums">{{ chf(person.total) }}</span>
          <BaseButton
            v-if="person.projects.length > 1"
            variant="secondary"
            :loading="busy === `all-${person.payer_type}-${person.payer_id}`"
            @click="
              settle(
                `all-${person.payer_type}-${person.payer_id}`,
                person.projects.flatMap((p) => p.transactions),
              )
            "
          >
            Tout rembourser
          </BaseButton>
        </div>
      </div>
      <ul class="mt-3 divide-y divide-line">
        <li
          v-for="entry in person.projects"
          :key="entry.project"
          class="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"
        >
          <span class="inline-flex items-center gap-2">
            <ColorDot :color="entry.project_color" />
            {{ entry.project_name }}
            <span class="text-muted">
              · {{ entry.transactions.length }} dépense{{
                entry.transactions.length > 1 ? 's' : ''
              }}
            </span>
          </span>
          <span class="flex items-center gap-3">
            <span class="tabular-nums">{{ chf(entry.total) }}</span>
            <BaseButton
              variant="ghost"
              :loading="busy === `${person.payer_type}-${person.payer_id}-${entry.project}`"
              @click="
                settle(
                  `${person.payer_type}-${person.payer_id}-${entry.project}`,
                  entry.transactions,
                )
              "
            >
              Marquer remboursé
            </BaseButton>
          </span>
        </li>
      </ul>
    </li>
  </ul>
</template>

<script setup lang="ts">
/**
 * Budget of a project (SPEC §13): planned versus actual per category, own
 * figures or with the sub-projects. Editors of the money type the planned
 * amounts straight into the grid; each cell saves on blur.
 */
import { computed, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { type Budget, type Category, financeApi, type TransactionKind } from '@/api/finance'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useUiStore } from '@/stores/ui'
import { KIND_LABELS } from '@/utils/finance'
import { chf, parseAmount, percentOf } from '@/utils/money'

const props = defineProps<{
  projectId: number
  workspaceId: number
  canEdit: boolean
  hasChildren: boolean
}>()
const emit = defineEmits<{ changed: [] }>()

const ui = useUiStore()
const budget = ref<Budget | null>(null)
const categories = ref<Category[]>([])
const scope = ref<'own' | 'with_children'>('own')
const adding = ref(false)
const newCategory = ref('')
const newKind = ref<TransactionKind>('expense')
const drafts = ref<Record<string, string>>({})

const SCOPES = [
  { value: 'own' as const, label: 'Ce projet' },
  { value: 'with_children' as const, label: 'Avec les sous-projets' },
]

async function load() {
  ;[budget.value, categories.value] = await Promise.all([
    financeApi.budget(props.projectId),
    financeApi.categories(props.workspaceId),
  ])
  drafts.value = {}
}
watch(() => props.projectId, load, { immediate: true })

const lines = computed(() =>
  (budget.value?.lines ?? []).map((line) => {
    const planned = scope.value === 'own' ? line.planned : line.planned_with_children
    const actual = scope.value === 'own' ? line.actual : line.actual_with_children
    return {
      ...line,
      key: `${line.kind}-${line.category}`,
      plannedShown: planned,
      actualShown: actual,
    }
  }),
)
const totals = computed(() => budget.value?.totals[scope.value])
const missingCategories = computed(() => {
  const used = new Set(lines.value.filter((l) => l.kind === newKind.value).map((l) => l.category))
  return categories.value.filter((c) => !used.has(c.id))
})
const addOptions = computed(() => [
  { value: '', label: 'Catégorie…' },
  ...missingCategories.value.map((c) => ({ value: String(c.id), label: c.name })),
])
const kindOptions = (Object.keys(KIND_LABELS) as TransactionKind[]).map((value) => ({
  value,
  label: KIND_LABELS[value],
}))

async function saveLine(category: number, kind: TransactionKind, raw: string) {
  const amount = raw.trim() === '' ? '0.00' : parseAmount(raw)
  if (amount === null && raw.trim() !== '0') {
    ui.toast('Montant invalide.', 'error')
    return
  }
  try {
    await financeApi.setBudgetLine(props.projectId, category, kind, amount ?? '0.00')
    await load()
    emit('changed')
  } catch (error) {
    ui.toast(
      error instanceof ApiError ? error.message : "Le budget n'a pas été enregistré.",
      'error',
    )
  }
}

async function addLine() {
  if (!newCategory.value) return
  await saveLine(Number(newCategory.value), newKind.value, '0')
  newCategory.value = ''
  adding.value = false
}
</script>

<template>
  <section class="rounded-2xl border border-line p-4">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-sm font-semibold">Budget</h2>
      <SegmentedControl v-if="hasChildren" v-model="scope" label="Périmètre" :options="SCOPES" />
    </div>

    <SkeletonBlock v-if="!budget" class="h-32" />

    <template v-else>
      <p v-if="!lines.length" class="text-sm text-muted">
        Aucune ligne de budget.
        {{ canEdit ? 'Ajoute une catégorie pour poser un prévisionnel.' : '' }}
      </p>
      <table v-else class="w-full text-sm">
        <thead class="text-xs text-muted">
          <tr>
            <th class="pb-1 text-left font-medium">Catégorie</th>
            <th class="pb-1 text-right font-medium">Prévu</th>
            <th class="pb-1 text-right font-medium">Réel</th>
            <th class="hidden pb-1 pl-3 text-left font-medium sm:table-cell">Avancement</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="line in lines" :key="line.key" class="border-t border-line">
            <td class="py-1.5 pr-2">
              {{ line.name }}
              <span class="ml-1 text-xs text-muted">{{ KIND_LABELS[line.kind] }}</span>
            </td>
            <td class="py-1.5 text-right tabular-nums">
              <input
                v-if="canEdit && scope === 'own'"
                :value="drafts[line.key] ?? line.planned"
                inputmode="decimal"
                class="h-8 w-28 rounded-md border border-line bg-surface px-2 text-right text-sm"
                :aria-label="`Prévu pour ${line.name}`"
                @input="drafts[line.key] = ($event.target as HTMLInputElement).value"
                @change="
                  saveLine(line.category, line.kind, ($event.target as HTMLInputElement).value)
                "
              />
              <span v-else>{{ chf(line.plannedShown) }}</span>
            </td>
            <td
              class="py-1.5 text-right tabular-nums"
              :class="
                line.kind === 'expense' && Number(line.actualShown) > Number(line.plannedShown)
                  ? 'font-semibold text-danger'
                  : ''
              "
            >
              {{ chf(line.actualShown) }}
            </td>
            <td class="hidden py-1.5 pl-3 sm:table-cell">
              <div
                class="h-1.5 w-full overflow-hidden rounded-full bg-surface-2"
                aria-hidden="true"
              >
                <div
                  class="h-full rounded-full"
                  :class="
                    line.kind === 'expense' && Number(line.actualShown) > Number(line.plannedShown)
                      ? 'bg-danger'
                      : 'bg-accent'
                  "
                  :style="{ width: `${percentOf(line.actualShown, line.plannedShown)}%` }"
                />
              </div>
            </td>
          </tr>
        </tbody>
        <tfoot v-if="totals" class="text-sm font-semibold">
          <tr class="border-t-2 border-fg">
            <td class="pt-2">Dépenses</td>
            <td class="pt-2 text-right tabular-nums">{{ chf(totals.planned_expense) }}</td>
            <td class="pt-2 text-right tabular-nums">{{ chf(totals.actual_expense) }}</td>
            <td class="hidden sm:table-cell" />
          </tr>
          <tr>
            <td class="pt-1">Recettes</td>
            <td class="pt-1 text-right tabular-nums">{{ chf(totals.planned_income) }}</td>
            <td class="pt-1 text-right tabular-nums">{{ chf(totals.actual_income) }}</td>
            <td class="hidden sm:table-cell" />
          </tr>
        </tfoot>
      </table>

      <div v-if="canEdit" class="mt-3">
        <form v-if="adding" class="flex flex-wrap items-end gap-2" @submit.prevent="addLine">
          <div class="min-w-40 flex-1">
            <BaseSelect v-model="newCategory" label="Catégorie" :options="addOptions" />
          </div>
          <div class="w-36">
            <BaseSelect v-model="newKind" label="Nature" :options="kindOptions" />
          </div>
          <BaseButton type="submit" variant="secondary" :disabled="!newCategory"
            >Ajouter</BaseButton
          >
          <BaseButton variant="ghost" @click="adding = false">Annuler</BaseButton>
        </form>
        <BaseButton v-else variant="secondary" @click="adding = true">Ajouter une ligne</BaseButton>
      </div>
    </template>
  </section>
</template>

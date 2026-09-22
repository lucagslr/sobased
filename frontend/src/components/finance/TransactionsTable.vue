<script setup lang="ts">
/**
 * The filterable table of transactions with its period, summary and exports.
 * Used by the global Compta page (a workspace or all of them) and by the
 * Compta tab of a project (the project and its sub-projects).
 *
 * The exports use the very same filters: what is listed is what is exported.
 */
import { Download, Plus, Search } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

import {
  type Category,
  financeApi,
  type FinanceSummary,
  type Transaction,
  type TransactionFilters,
} from '@/api/finance'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { KIND_LABELS, type PeriodPreset, periodBounds } from '@/utils/finance'

import CategoryTotals from './CategoryTotals.vue'
import FinanceSummaryCards from './FinanceSummaryCards.vue'
import TransactionRow from './TransactionRow.vue'

const props = defineProps<{
  /** Fixed part of the filters: the scope (project + descendants, workspace). */
  scope: TransactionFilters
  /** Workspace of the categories filter (undefined with "Tous les espaces"). */
  workspaceId?: number
  /** The user may create transactions somewhere in the scope. */
  canCreate: boolean
  showProject?: boolean
}>()
const emit = defineEmits<{ open: [id: number]; create: [] }>()

const transactions = ref<Transaction[] | null>(null)
const total = ref(0)
const summary = ref<FinanceSummary | null>(null)
const categories = ref<Category[]>([])
const period = ref<PeriodPreset>('year')
const kind = ref<'' | 'expense' | 'income'>('')
const category = ref('')
const status = ref<'' | 'needs_receipt' | 'to_pay' | 'to_reimburse'>('')
const search = ref('')
const page = ref(1)

const PERIODS: { value: PeriodPreset; label: string }[] = [
  { value: 'month', label: 'Mois' },
  { value: 'quarter', label: 'Trimestre' },
  { value: 'year', label: 'Année' },
  { value: 'all', label: 'Tout' },
]
const kindOptions = [
  { value: '', label: 'Dépenses et recettes' },
  { value: 'expense', label: KIND_LABELS.expense + 's' },
  { value: 'income', label: KIND_LABELS.income + 's' },
]
const statusOptions = [
  { value: '', label: 'Tous les statuts' },
  { value: 'needs_receipt', label: 'À justifier' },
  { value: 'to_pay', label: 'À payer' },
  { value: 'to_reimburse', label: 'À rembourser' },
]
const categoryOptions = computed(() => [
  { value: '', label: 'Toutes les catégories' },
  ...categories.value.map((c) => ({ value: String(c.id), label: c.name })),
])

const filters = computed<TransactionFilters>(() => {
  const bounds = periodBounds(period.value)
  return {
    ...props.scope,
    date_after: bounds.after || undefined,
    date_before: bounds.before || undefined,
    kind: kind.value || undefined,
    category: category.value ? Number(category.value) : undefined,
    needs_receipt: status.value === 'needs_receipt' ? true : undefined,
    payment_status: status.value === 'to_pay' ? 'to_pay' : undefined,
    to_reimburse: status.value === 'to_reimburse' ? true : undefined,
    search: search.value.trim() || undefined,
  }
})

async function load() {
  const [list, totals] = await Promise.all([
    financeApi.transactions({ ...filters.value, page: page.value }),
    financeApi.summary(filters.value),
  ])
  transactions.value = list.results
  total.value = list.count
  summary.value = totals
}
watch(filters, () => ((page.value = 1), load()), { immediate: true })
watch(page, load)
watch(
  () => props.workspaceId,
  async (workspace) => {
    categories.value = workspace ? await financeApi.categories(workspace) : []
  },
  { immediate: true },
)
defineExpose({ reload: load })

const byCategory = computed(() =>
  (summary.value?.by_category ?? []).map((row) => ({ ...row, key: row.category })),
)
const byProject = computed(() =>
  (summary.value?.by_project ?? []).map((row) => ({ ...row, key: row.project, name: '' })),
)
function exportUrl(kind: 'xlsx' | 'pdf' | 'receipts') {
  return financeApi.exportUrl(kind, filters.value)
}
</script>

<template>
  <div class="space-y-5">
    <div class="flex flex-wrap items-center gap-3">
      <SegmentedControl v-model="period" label="Période" :options="PERIODS" />
      <BaseButton v-if="canCreate" @click="emit('create')">
        <Plus class="size-4" aria-hidden="true" /> Nouvelle écriture
      </BaseButton>
      <div class="ml-auto flex flex-wrap gap-2">
        <a
          v-for="item in [
            { kind: 'xlsx' as const, label: 'Excel' },
            { kind: 'pdf' as const, label: 'PDF' },
            { kind: 'receipts' as const, label: 'Justificatifs (ZIP)' },
          ]"
          :key="item.kind"
          :href="exportUrl(item.kind)"
          class="inline-flex h-9 items-center gap-1.5 rounded-lg border border-line px-3 text-sm font-medium hover:bg-surface-2"
          download
        >
          <Download class="size-4" aria-hidden="true" /> {{ item.label }}
        </a>
      </div>
    </div>

    <FinanceSummaryCards v-if="summary" :summary="summary" />
    <div v-else class="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <SkeletonBlock v-for="n in 4" :key="n" class="h-20" />
    </div>

    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <BaseSelect v-model="kind" label="Nature" :options="kindOptions" />
      <BaseSelect v-model="category" label="Catégorie" :options="categoryOptions" />
      <BaseSelect v-model="status" label="Statut" :options="statusOptions" />
      <label class="block">
        <span class="mb-1.5 block text-sm font-medium">Recherche</span>
        <span class="relative block">
          <Search
            class="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted"
            aria-hidden="true"
          />
          <input
            v-model="search"
            type="search"
            placeholder="Libellé, fournisseur…"
            class="h-10 w-full rounded-lg border border-line bg-surface pr-3 pl-9 text-[15px] placeholder:text-muted"
          />
        </span>
      </label>
    </div>

    <div v-if="transactions === null" class="space-y-2">
      <SkeletonBlock v-for="n in 5" :key="n" class="h-12" />
    </div>
    <EmptyState
      v-else-if="!transactions.length"
      :icon="Search"
      title="Aucune écriture"
      text="Rien sur cette période avec ces filtres."
    />
    <template v-else>
      <ul class="border-t border-line">
        <TransactionRow
          v-for="item in transactions"
          :key="item.id"
          :transaction="item"
          :show-project="showProject"
          @open="emit('open', item.id)"
        />
      </ul>
      <div v-if="total > transactions.length" class="flex items-center justify-between text-sm">
        <span class="text-muted">{{ transactions.length }} sur {{ total }}</span>
        <span class="flex gap-2">
          <BaseButton variant="secondary" :disabled="page <= 1" @click="page -= 1">
            Précédent
          </BaseButton>
          <BaseButton variant="secondary" :disabled="page * 100 >= total" @click="page += 1">
            Suivant
          </BaseButton>
        </span>
      </div>
    </template>

    <div
      v-if="summary && (byCategory.length || byProject.length)"
      class="grid gap-4 lg:grid-cols-2"
    >
      <CategoryTotals title="Par catégorie" :rows="byCategory" />
      <slot name="by-project" :rows="byProject" />
    </div>
  </div>
</template>

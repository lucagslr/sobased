<script setup lang="ts">
/**
 * "Compta" tab of a project (shown only with can_view_finance): the budget,
 * the transactions of the project and its sub-projects, the advances and the
 * recurring expenses, with the exports scoped to this branch.
 */
import { computed, ref } from 'vue'

import type { TransactionFilters } from '@/api/finance'
import type { Project } from '@/api/projects'
import AdvancesView from '@/components/finance/AdvancesView.vue'
import BudgetTable from '@/components/finance/BudgetTable.vue'
import CategoryTotals from '@/components/finance/CategoryTotals.vue'
import RecurringExpenseList from '@/components/finance/RecurringExpenseList.vue'
import TransactionPanel from '@/components/finance/TransactionPanel.vue'
import TransactionsTable from '@/components/finance/TransactionsTable.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import { useTransactionPanel } from '@/composables/useTransactionPanel'
import { useProjectsStore } from '@/stores/projects'

type Tab = 'transactions' | 'budget' | 'advances' | 'recurring'
const TABS: { value: Tab; label: string }[] = [
  { value: 'transactions', label: 'Écritures' },
  { value: 'budget', label: 'Budget' },
  { value: 'advances', label: 'Qui doit quoi' },
  { value: 'recurring', label: 'Frais récurrents' },
]

const props = defineProps<{ project: Project }>()

const projects = useProjectsStore()
const { transactionId, openTransaction, closeTransaction } = useTransactionPanel()

const tab = ref<Tab>('transactions')
const creating = ref(false)
const table = ref<InstanceType<typeof TransactionsTable> | null>(null)

const scope = computed<TransactionFilters>(() => ({
  project: props.project.id,
  include_descendants: true,
}))
const hasChildren = computed(() => projects.childrenOf(props.project.id).length > 0)
const editableProjects = computed(() => {
  const branch = [props.project.id]
  const walk = (id: number) => {
    for (const child of projects.childrenOf(id)) {
      branch.push(child.id)
      walk(child.id)
    }
  }
  walk(props.project.id)
  return branch.filter((id) => projects.byId.get(id)?.can_edit_finance)
})
const projectName = (id: number) => projects.byId.get(id)?.name ?? `#${id}`

const panelOpen = computed({
  get: () => transactionId.value !== null || creating.value,
  set: (value) => {
    if (value) return
    creating.value = false
    if (transactionId.value !== null) closeTransaction()
  },
})
</script>

<template>
  <div class="mb-5">
    <SegmentedControl v-model="tab" label="Section de la compta" :options="TABS" />
  </div>

  <TransactionsTable
    v-if="tab === 'transactions'"
    ref="table"
    :scope="scope"
    :workspace-id="project.workspace"
    :can-create="!!project.can_edit_finance"
    :show-project="hasChildren"
    @open="openTransaction"
    @create="creating = true"
  >
    <template #by-project="{ rows }">
      <CategoryTotals
        v-if="hasChildren"
        title="Par projet"
        :rows="rows.map((r) => ({ ...r, name: projectName(Number(r.key)) }))"
      />
    </template>
  </TransactionsTable>

  <BudgetTable
    v-else-if="tab === 'budget'"
    :project-id="project.id"
    :workspace-id="project.workspace"
    :can-edit="!!project.can_edit_finance"
    :has-children="hasChildren"
  />

  <AdvancesView v-else-if="tab === 'advances'" :project-id="project.id" />

  <RecurringExpenseList
    v-else
    :project="project.id"
    :editable-projects="editableProjects"
    :show-project="hasChildren"
  />

  <TransactionPanel
    v-model:open="panelOpen"
    :transaction-id="transactionId"
    :create-in="creating ? project.id : null"
    @changed="table?.reload()"
  />
</template>

<script setup lang="ts">
/**
 * Compta globale (SPEC §15, page 7): the filterable table, the syntheses,
 * « Qui doit quoi à qui », the recurring expenses and the exports, over the
 * selected workspace or all of them. Only projects where I have
 * can_view_finance ever show up; the server enforces it.
 */
import { computed, ref, watch } from 'vue'

import { type TransactionFilters } from '@/api/finance'
import AdvancesView from '@/components/finance/AdvancesView.vue'
import CategoryTotals from '@/components/finance/CategoryTotals.vue'
import RecurringExpenseList from '@/components/finance/RecurringExpenseList.vue'
import TransactionPanel from '@/components/finance/TransactionPanel.vue'
import TransactionsTable from '@/components/finance/TransactionsTable.vue'
import WorkspaceSwitcher from '@/components/layout/WorkspaceSwitcher.vue'
import WorkspaceFormPanel from '@/components/projects/WorkspaceFormPanel.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import { useTransactionPanel } from '@/composables/useTransactionPanel'
import { useProjectsStore } from '@/stores/projects'
import { useWorkspacesStore } from '@/stores/workspaces'

type Tab = 'transactions' | 'advances' | 'recurring'
const TABS: { value: Tab; label: string }[] = [
  { value: 'transactions', label: 'Écritures' },
  { value: 'advances', label: 'Qui doit quoi' },
  { value: 'recurring', label: 'Frais récurrents' },
]

const projects = useProjectsStore()
const workspaces = useWorkspacesStore()
const { transactionId, openTransaction, closeTransaction } = useTransactionPanel()

const tab = ref<Tab>('transactions')
const creatingIn = ref('')
const creating = ref(false)
const workspacePanel = ref(false)
const table = ref<InstanceType<typeof TransactionsTable> | null>(null)

watch(
  () => projects.loaded,
  (loaded) => !loaded && projects.load(),
  { immediate: true },
)

const workspaceId = computed(() =>
  workspaces.selection === 'all' ? undefined : workspaces.selection,
)
const scope = computed<TransactionFilters>(() => ({ workspace: workspaceId.value }))
// Projects where I may write money, in the current scope.
const editableProjects = computed(() =>
  projects.nodes
    .filter((n) => n.can_edit_finance && (!workspaceId.value || n.workspace === workspaceId.value))
    .map((n) => n.id),
)
const projectOptions = computed(() => [
  { value: '', label: 'Dans quel projet ?' },
  ...editableProjects.value.map((id) => {
    const node = projects.byId.get(id)!
    return { value: String(id), label: '· '.repeat(node.depth - 1) + node.name }
  }),
])
const projectName = (id: number) => projects.byId.get(id)?.name ?? `#${id}`

function startCreate() {
  creatingIn.value = editableProjects.value.length === 1 ? String(editableProjects.value[0]) : ''
  creating.value = true
}

const panelOpen = computed({
  get: () => transactionId.value !== null || (creating.value && !!creatingIn.value),
  set: (value) => {
    if (value) return
    creating.value = false
    if (transactionId.value !== null) closeTransaction()
  },
})
</script>

<template>
  <PageHeader
    title="Compta"
    :subtitle="workspaces.current ? workspaces.current.name : 'Tous les espaces'"
  />

  <!-- Below 1024px there is no sidebar: the workspace filter lives here. -->
  <div class="mb-4 lg:hidden">
    <WorkspaceSwitcher @create="workspacePanel = true" />
  </div>

  <div class="mb-5">
    <SegmentedControl v-model="tab" label="Section de la compta" :options="TABS" />
  </div>

  <template v-if="tab === 'transactions'">
    <!-- Which project? Only asked when several are possible. -->
    <div v-if="creating && !creatingIn" class="mb-4 max-w-sm rounded-2xl border border-line p-4">
      <BaseSelect v-model="creatingIn" label="Nouvelle écriture" :options="projectOptions" />
    </div>
    <TransactionsTable
      ref="table"
      :scope="scope"
      :workspace-id="workspaceId"
      :can-create="editableProjects.length > 0"
      show-project
      @open="openTransaction"
      @create="startCreate"
    >
      <template #by-project="{ rows }">
        <CategoryTotals
          title="Par projet"
          :rows="rows.map((r) => ({ ...r, name: projectName(Number(r.key)) }))"
        />
      </template>
    </TransactionsTable>
  </template>

  <AdvancesView v-else-if="tab === 'advances'" :workspace-id="workspaceId" />

  <RecurringExpenseList
    v-else
    :workspace="workspaceId"
    :editable-projects="editableProjects"
    show-project
  />

  <TransactionPanel
    v-model:open="panelOpen"
    :transaction-id="transactionId"
    :create-in="creating && creatingIn ? Number(creatingIn) : null"
    @changed="table?.reload()"
  />
  <WorkspaceFormPanel v-model:open="workspacePanel" />
</template>

<script setup lang="ts">
/**
 * A recurring expense (SPEC §13): Studio One, a software, the bank card…
 * Each period the nightly job creates its transaction « À payer ».
 * Changing it only affects future periods.
 */
import { Trash2 } from 'lucide-vue-next'
import { computed, reactive, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import {
  type Category,
  financeApi,
  type Frequency,
  type RecurringExpense,
  type RecurringExpensePayload,
} from '@/api/finance'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import BaseSwitch from '@/components/ui/BaseSwitch.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import FormError from '@/components/ui/FormError.vue'
import SidePanel from '@/components/ui/SidePanel.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { describeSchedule, FREQUENCY_LABELS, MONTH_NAMES } from '@/utils/finance'
import { parseAmount } from '@/utils/money'
import { localDateKey } from '@/utils/tasks'

const props = defineProps<{
  expense?: RecurringExpense | null
  /** Creation: projects (with can_edit_finance) the expense may go to. */
  projectChoices?: number[]
}>()
const emit = defineEmits<{ saved: []; deleted: [] }>()
const open = defineModel<boolean>('open', { required: true })

const projects = useProjectsStore()
const ui = useUiStore()
const { loading, error, fieldErrors, submit } = useFormSubmit()
const categories = ref<Category[]>([])
const deleteDialog = ref(false)

const form = reactive({
  project: '',
  label: '',
  amount: '',
  category: '',
  vendor: '',
  frequency: 'monthly' as Frequency,
  day: '1',
  month: '1',
  start_date: localDateKey(new Date()),
  end_date: '',
  is_active: true,
})

const projectId = computed(() => props.expense?.project ?? (Number(form.project) || null))
const project = computed(() => (projectId.value ? projects.byId.get(projectId.value) : undefined))
const canEdit = computed(() => !!project.value?.can_edit_finance)

const projectOptions = computed(() => [
  { value: '', label: 'Choisir un projet…' },
  ...(props.projectChoices ?? [])
    .map((id) => projects.byId.get(id))
    .filter((node) => !!node)
    .map((node) => ({ value: String(node!.id), label: node!.name })),
])
const categoryOptions = computed(() => [
  { value: '', label: 'Choisir une catégorie…' },
  ...categories.value.map((c) => ({ value: String(c.id), label: c.name })),
])
const frequencyOptions = (Object.keys(FREQUENCY_LABELS) as Frequency[]).map((value) => ({
  value,
  label: FREQUENCY_LABELS[value],
}))
const dayOptions = Array.from({ length: 31 }, (_, i) => ({
  value: String(i + 1),
  label: String(i + 1),
}))
const monthOptions = MONTH_NAMES.map((name, i) => ({ value: String(i + 1), label: name }))
const schedule = computed(() =>
  describeSchedule(form.frequency, Number(form.day) || 1, Number(form.month) || 1),
)

watch(
  () => project.value?.workspace,
  async (workspace) => {
    categories.value = workspace ? await financeApi.categories(workspace) : []
    if (!form.category && !props.expense) {
      const fallback = categories.value.find((c) => c.name === 'Autre') ?? categories.value[0]
      if (fallback) form.category = String(fallback.id)
    }
  },
  { immediate: true },
)

function fill(source: RecurringExpense | null | undefined) {
  Object.assign(form, {
    project: source ? String(source.project) : (props.projectChoices?.[0]?.toString() ?? ''),
    label: source?.label ?? '',
    amount: source?.amount ?? '',
    category: source ? String(source.category) : '',
    vendor: source?.vendor ?? '',
    frequency: source?.frequency ?? 'monthly',
    day: String(source?.day ?? 1),
    month: String(source?.month ?? 1),
    start_date: source?.start_date ?? localDateKey(new Date()),
    end_date: source?.end_date ?? '',
    is_active: source?.is_active ?? true,
  })
}
watch(
  () => [open.value, props.expense] as const,
  ([isOpen]) => {
    if (!isOpen) return
    error.value = ''
    fieldErrors.value = {}
    fill(props.expense)
  },
  { immediate: true },
)

function payload(): RecurringExpensePayload {
  return {
    label: form.label.trim(),
    amount: parseAmount(form.amount) ?? form.amount,
    category: Number(form.category) || undefined,
    vendor: form.vendor.trim(),
    frequency: form.frequency,
    day: Number(form.day),
    month: Number(form.month),
    start_date: form.start_date,
    end_date: form.end_date || null,
    is_active: form.is_active,
  }
}

async function save() {
  const ok = await submit(async () => {
    if (props.expense) await financeApi.updateRecurringExpense(props.expense.id, payload())
    else await financeApi.createRecurringExpense({ ...payload(), project: Number(form.project) })
  })
  if (!ok) return
  ui.toast(props.expense ? 'Frais récurrent enregistré' : 'Frais récurrent créé', 'success')
  open.value = false
  emit('saved')
}

async function remove() {
  deleteDialog.value = false
  if (!props.expense) return
  try {
    await financeApi.removeRecurringExpense(props.expense.id)
    ui.toast('Frais récurrent supprimé', 'success')
    open.value = false
    emit('deleted')
  } catch (caught) {
    ui.toast(caught instanceof ApiError ? caught.message : 'La suppression a échoué.', 'error')
  }
}
</script>

<template>
  <SidePanel
    v-model:open="open"
    :title="expense ? expense.label : 'Nouveau frais récurrent'"
    :description="project?.name"
  >
    <form id="recurring-form" class="space-y-5" @submit.prevent="save">
      <FormError :message="error || fieldErrors.category?.[0]" />
      <fieldset :disabled="!!expense && !canEdit" class="space-y-5">
        <BaseSelect
          v-if="!expense"
          v-model="form.project"
          label="Projet"
          :options="projectOptions"
          :errors="fieldErrors.project"
        />
        <BaseInput
          v-model="form.label"
          label="Libellé"
          placeholder="Studio One, Adobe, carte…"
          required
          :errors="fieldErrors.label"
        />
        <div class="grid grid-cols-2 gap-4">
          <BaseInput
            v-model="form.amount"
            label="Montant (CHF)"
            inputmode="decimal"
            required
            :errors="fieldErrors.amount"
          />
          <BaseSelect v-model="form.category" label="Catégorie" :options="categoryOptions" />
        </div>
        <BaseInput v-model="form.vendor" label="Fournisseur" placeholder="Texte libre" />
        <div class="grid grid-cols-2 gap-4">
          <BaseSelect v-model="form.frequency" label="Fréquence" :options="frequencyOptions" />
          <BaseSelect
            v-model="form.day"
            label="Jour"
            :options="dayOptions"
            :errors="fieldErrors.day"
          />
          <BaseSelect
            v-if="form.frequency === 'yearly'"
            v-model="form.month"
            label="Mois"
            :options="monthOptions"
          />
        </div>
        <p class="text-sm text-muted">Généré {{ schedule }}, au statut « À payer ».</p>
        <div class="grid grid-cols-2 gap-4">
          <BaseInput
            v-model="form.start_date"
            label="Début"
            type="date"
            required
            :errors="fieldErrors.start_date"
          />
          <BaseInput
            v-model="form.end_date"
            label="Fin (facultative)"
            type="date"
            :errors="fieldErrors.end_date"
          />
        </div>
        <BaseSwitch
          v-if="expense"
          v-model="form.is_active"
          label="Actif"
          description="Désactivé, il ne génère plus rien ; les écritures passées restent."
        />
      </fieldset>
    </form>

    <template #footer>
      <button
        v-if="expense && canEdit"
        type="button"
        class="mr-auto rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-danger"
        aria-label="Supprimer le frais récurrent"
        @click="deleteDialog = true"
      >
        <Trash2 class="size-4" aria-hidden="true" />
      </button>
      <BaseButton variant="secondary" @click="open = false">Fermer</BaseButton>
      <BaseButton v-if="!expense || canEdit" type="submit" form="recurring-form" :loading="loading">
        {{ expense ? 'Enregistrer' : 'Créer' }}
      </BaseButton>
    </template>
  </SidePanel>

  <ConfirmDialog
    v-model:open="deleteDialog"
    :title="`Supprimer « ${expense?.label} » ?`"
    confirm-label="Supprimer"
    danger
    @confirm="remove"
  >
    <p>Les écritures déjà générées restent dans la compta.</p>
  </ConfirmDialog>
</template>

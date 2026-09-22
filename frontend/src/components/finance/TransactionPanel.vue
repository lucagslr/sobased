<script setup lang="ts">
/**
 * Create or edit a transaction (SPEC §13). The receipt is uploaded from the
 * same form (`capture="environment"` opens the camera on a phone); an
 * expense without one stays « À justifier » and red until it gets one.
 *
 * Editable with `can_edit_finance` on the project; read-only otherwise.
 */
import { Camera, FileText, Paperclip, Trash2, X } from 'lucide-vue-next'
import { computed, reactive, ref, watch } from 'vue'

import type { PublicUser } from '@/api/auth'
import { ApiError } from '@/api/client'
import { type Contact, contactsApi } from '@/api/contacts'
import {
  type Category,
  financeApi,
  type PaymentStatus,
  type Transaction,
  type TransactionKind,
  type TransactionPayload,
} from '@/api/finance'
import { membersApi } from '@/api/projects'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import BaseSwitch from '@/components/ui/BaseSwitch.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import FormError from '@/components/ui/FormError.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import SidePanel from '@/components/ui/SidePanel.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { KIND_LABELS, PAYMENT_STATUS_LABELS } from '@/utils/finance'
import { chf, parseAmount } from '@/utils/money'
import { localDateKey } from '@/utils/tasks'

import TransactionStatusBadge from './TransactionStatusBadge.vue'

const RECEIPT_MAX_MB = 20

const props = defineProps<{
  transactionId?: number | null
  /** Creation: the project the transaction goes to. */
  createIn?: number | null
}>()
const emit = defineEmits<{ changed: [] }>()
const open = defineModel<boolean>('open', { required: true })

const projects = useProjectsStore()
const ui = useUiStore()
const { loading, error, fieldErrors, submit } = useFormSubmit()

const item = ref<Transaction | null>(null)
const ready = ref(false)
const categories = ref<Category[]>([])
const members = ref<PublicUser[]>([])
const contacts = ref<Contact[]>([])
const receiptFile = ref<File | null>(null)
const dropReceipt = ref(false)
const deleteDialog = ref(false)
const receiptInput = ref<HTMLInputElement | null>(null)

const form = reactive({
  kind: 'expense' as TransactionKind,
  amount: '',
  date: localDateKey(new Date()),
  category: '',
  label: '',
  vendor: '',
  contact: '',
  payment_status: 'paid' as PaymentStatus,
  payer: '' as string, // "" | "u:<username>" | "c:<contact id>"
  to_reimburse: false,
  reimbursed_on: '',
})

const projectId = computed(() => item.value?.project ?? props.createIn ?? null)
const project = computed(() => (projectId.value ? projects.byId.get(projectId.value) : undefined))
const canEdit = computed(() => !!project.value?.can_edit_finance)
const isExpense = computed(() => form.kind === 'expense')

const kindOptions = (Object.keys(KIND_LABELS) as TransactionKind[]).map((value) => ({
  value,
  label: KIND_LABELS[value],
}))
const statusOptions = (Object.keys(PAYMENT_STATUS_LABELS) as PaymentStatus[]).map((value) => ({
  value,
  label: PAYMENT_STATUS_LABELS[value],
}))
const categoryOptions = computed(() => [
  { value: '', label: 'Choisir une catégorie…' },
  ...categories.value.map((c) => ({ value: String(c.id), label: c.name })),
])
const contactOptions = computed(() => [
  { value: '', label: '—' },
  ...contacts.value.map((c) => ({
    value: String(c.id),
    label: [c.display_name, c.organization].filter(Boolean).join(' · '),
  })),
])
const payerOptions = computed(() => [
  { value: '', label: 'Le projet / l’association' },
  ...members.value.map((u) => ({ value: `u:${u.username}`, label: u.display_name })),
  ...contacts.value.map((c) => ({ value: `c:${c.id}`, label: `${c.display_name} (contact)` })),
])
const amountPreview = computed(() => {
  const parsed = parseAmount(form.amount)
  return parsed ? chf(parsed) : ''
})

function fill(source: Transaction | null) {
  Object.assign(form, {
    kind: source?.kind ?? 'expense',
    amount: source ? source.amount : '',
    date: source?.date ?? localDateKey(new Date()),
    category: source ? String(source.category) : '',
    label: source?.label ?? '',
    vendor: source?.vendor ?? '',
    contact: source?.contact ? String(source.contact) : '',
    payment_status: source?.payment_status ?? 'paid',
    payer: source?.payer
      ? source.payer.type === 'user'
        ? `u:${source.payer.username}`
        : `c:${source.payer.id}`
      : '',
    to_reimburse: source?.to_reimburse ?? false,
    reimbursed_on: source?.reimbursed_on ?? '',
  })
  receiptFile.value = null
  dropReceipt.value = false
}

async function load() {
  ready.value = false
  error.value = ''
  fieldErrors.value = {}
  item.value = null
  try {
    if (props.transactionId) item.value = await financeApi.transaction(props.transactionId)
    fill(item.value)
    if (!projects.loaded) await projects.load()
    if (project.value) {
      const [cats, effective, book] = await Promise.all([
        financeApi.categories(project.value.workspace),
        membersApi.list({ project: project.value.id }),
        contactsApi.list({ workspace: project.value.workspace }),
      ])
      categories.value = cats
      members.value = effective.map((member) => member.user)
      contacts.value = book
      if (!form.category && !item.value) {
        const fallback = cats.find((c) => c.name === 'Autre') ?? cats[0]
        if (fallback) form.category = String(fallback.id)
      }
    }
    ready.value = true
  } catch (caught) {
    open.value = false
    ui.toast(
      caught instanceof ApiError && caught.status === 404
        ? "Cette écriture n'existe plus, ou tu n'y as pas accès."
        : "L'écriture ne peut pas être ouverte.",
      'error',
    )
  }
}

watch(
  () => [open.value, props.transactionId, props.createIn] as const,
  ([isOpen]) => isOpen && load(),
  { immediate: true },
)

// An income is never advanced by someone nor "to reimburse".
watch(isExpense, (expense) => {
  if (!expense) {
    form.payer = ''
    form.to_reimburse = false
    form.reimbursed_on = ''
  }
})

function onReceiptPicked(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0] ?? null
  if (file && file.size > RECEIPT_MAX_MB * 1024 * 1024) {
    ui.toast(`Justificatif trop lourd (${RECEIPT_MAX_MB} Mo max).`, 'error')
    if (receiptInput.value) receiptInput.value.value = ''
    return
  }
  receiptFile.value = file
  dropReceipt.value = false
}

function payload(): TransactionPayload {
  const amount = parseAmount(form.amount)
  const body: TransactionPayload = {
    kind: form.kind,
    amount: amount ?? form.amount, // let the server word the error
    date: form.date,
    category: Number(form.category) || undefined,
    label: form.label.trim(),
    vendor: form.vendor.trim(),
    contact: form.contact ? Number(form.contact) : null,
    payment_status: form.payment_status,
    to_reimburse: isExpense.value && form.to_reimburse,
    reimbursed_on:
      isExpense.value && form.to_reimburse && form.reimbursed_on ? form.reimbursed_on : null,
  }
  if (isExpense.value) {
    body.paid_by_username = form.payer.startsWith('u:') ? form.payer.slice(2) : ''
    body.paid_by_contact = form.payer.startsWith('c:') ? Number(form.payer.slice(2)) : null
  }
  return body
}

async function save() {
  let saved: Transaction | undefined
  const ok = await submit(async () => {
    if (item.value) {
      if (dropReceipt.value && item.value.has_receipt) {
        await financeApi.removeReceipt(item.value.id)
      }
      saved = await financeApi.updateTransaction(item.value.id, payload(), receiptFile.value)
    } else {
      saved = await financeApi.createTransaction(
        { ...payload(), project: props.createIn! },
        receiptFile.value,
      )
    }
  })
  if (!ok || !saved) return
  const created = !item.value
  item.value = saved
  fill(saved)
  ui.toast(created ? 'Écriture enregistrée' : 'Écriture mise à jour', 'success')
  emit('changed')
  if (created) open.value = false
}

async function remove() {
  deleteDialog.value = false
  if (!item.value) return
  try {
    await financeApi.removeTransaction(item.value.id)
    ui.toast('Écriture supprimée', 'success')
    open.value = false
    emit('changed')
  } catch (caught) {
    ui.toast(caught instanceof ApiError ? caught.message : 'La suppression a échoué.', 'error')
  }
}

async function markPaid() {
  if (!item.value) return
  try {
    item.value = await financeApi.markPaid(item.value.id)
    fill(item.value)
    emit('changed')
  } catch (caught) {
    ui.toast(caught instanceof ApiError ? caught.message : 'Le statut est resté inchangé.', 'error')
  }
}
</script>

<template>
  <SidePanel
    v-model:open="open"
    :title="item ? KIND_LABELS[item.kind] : 'Nouvelle écriture'"
    :description="project?.name"
  >
    <div v-if="!ready" class="space-y-4">
      <SkeletonBlock class="h-10 w-full" />
      <SkeletonBlock class="h-24 w-full" />
    </div>

    <form v-else id="transaction-form" class="space-y-5" @submit.prevent="save">
      <FormError :message="error || fieldErrors.receipt?.[0] || fieldErrors.category?.[0]" />

      <div v-if="item" class="flex flex-wrap items-center gap-2">
        <TransactionStatusBadge :status="item.display_status" />
        <BaseButton
          v-if="item.payment_status === 'to_pay' && canEdit"
          variant="secondary"
          @click="markPaid"
        >
          Marquer payé
        </BaseButton>
      </div>

      <fieldset :disabled="!canEdit" class="space-y-5">
        <SegmentedControl v-model="form.kind" label="Nature" :options="kindOptions" />

        <div class="grid grid-cols-2 gap-4">
          <div>
            <BaseInput
              v-model="form.amount"
              label="Montant (CHF)"
              inputmode="decimal"
              placeholder="0.00"
              required
              :errors="fieldErrors.amount"
            />
            <p v-if="amountPreview" class="mt-1 text-xs text-muted">{{ amountPreview }}</p>
          </div>
          <BaseInput
            v-model="form.date"
            label="Date"
            type="date"
            required
            :errors="fieldErrors.date"
          />
        </div>

        <BaseInput
          v-model="form.label"
          label="Libellé"
          placeholder="Location du studio, cachet, subvention…"
          required
          :errors="fieldErrors.label"
        />
        <div class="grid grid-cols-2 gap-4">
          <BaseSelect v-model="form.category" label="Catégorie" :options="categoryOptions" />
          <BaseSelect v-model="form.payment_status" label="Paiement" :options="statusOptions" />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <BaseInput v-model="form.vendor" label="Fournisseur" placeholder="Texte libre" />
          <BaseSelect v-model="form.contact" label="Contact lié" :options="contactOptions" />
        </div>

        <!-- Expense advance (SPEC §13) -->
        <div v-if="isExpense" class="space-y-3 rounded-xl border border-line p-3">
          <BaseSelect v-model="form.payer" label="Payé par" :options="payerOptions" />
          <BaseSwitch
            v-model="form.to_reimburse"
            label="À rembourser"
            description="Une avance de frais : la personne doit être remboursée par le projet."
            :disabled="!canEdit || !form.payer"
          />
          <BaseInput
            v-if="form.to_reimburse"
            v-model="form.reimbursed_on"
            label="Remboursé le (vide = pas encore)"
            type="date"
            :errors="fieldErrors.reimbursed_on"
          />
        </div>

        <!-- Receipt: mandatory for an expense, uploaded here (camera on phones). -->
        <div v-if="isExpense">
          <p class="mb-1.5 text-sm font-medium">
            Justificatif
            <span class="font-normal text-muted">(image ou PDF, {{ RECEIPT_MAX_MB }} Mo max)</span>
          </p>
          <div
            v-if="item?.has_receipt && !dropReceipt && !receiptFile"
            class="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm"
          >
            <FileText class="size-4 shrink-0 text-muted" aria-hidden="true" />
            <a
              :href="item.receipt_url ?? '#'"
              target="_blank"
              rel="noopener"
              class="min-w-0 flex-1 truncate hover:underline"
            >
              {{ item.receipt_name || 'Justificatif' }}
            </a>
            <button
              v-if="canEdit"
              type="button"
              class="rounded p-1 text-muted hover:text-danger"
              aria-label="Retirer le justificatif"
              @click="dropReceipt = true"
            >
              <X class="size-4" aria-hidden="true" />
            </button>
          </div>
          <div
            v-else-if="receiptFile"
            class="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm"
          >
            <Paperclip class="size-4 shrink-0 text-muted" aria-hidden="true" />
            <span class="min-w-0 flex-1 truncate">{{ receiptFile.name }}</span>
            <button
              type="button"
              class="rounded p-1 text-muted hover:text-danger"
              aria-label="Annuler ce fichier"
              @click="((receiptFile = null), receiptInput && (receiptInput.value = ''))"
            >
              <X class="size-4" aria-hidden="true" />
            </button>
          </div>
          <div v-else-if="canEdit" class="flex flex-wrap gap-2">
            <label
              class="inline-flex h-9 cursor-pointer items-center gap-2 rounded-lg border border-line px-3 text-sm font-medium hover:bg-surface-2"
            >
              <Paperclip class="size-4" aria-hidden="true" /> Choisir un fichier
              <input
                ref="receiptInput"
                type="file"
                accept="image/*,application/pdf"
                class="sr-only"
                @change="onReceiptPicked"
              />
            </label>
            <label
              class="inline-flex h-9 cursor-pointer items-center gap-2 rounded-lg border border-line px-3 text-sm font-medium hover:bg-surface-2 sm:hidden"
            >
              <Camera class="size-4" aria-hidden="true" /> Photographier
              <input
                type="file"
                accept="image/*"
                capture="environment"
                class="sr-only"
                @change="onReceiptPicked"
              />
            </label>
            <p v-if="item" class="w-full text-xs text-danger">
              Sans justificatif, cette dépense reste « À justifier ».
            </p>
          </div>
          <p v-else class="text-sm text-muted">Aucun justificatif.</p>
        </div>
      </fieldset>

      <p v-if="item && !canEdit" class="text-sm text-muted">
        Tu peux consulter cette écriture, pas la modifier (option « éditer la compta »).
      </p>
    </form>

    <template v-if="ready && canEdit" #footer>
      <button
        v-if="item"
        type="button"
        class="mr-auto rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-danger"
        aria-label="Supprimer l'écriture"
        @click="deleteDialog = true"
      >
        <Trash2 class="size-4" aria-hidden="true" />
      </button>
      <BaseButton variant="secondary" @click="open = false">Fermer</BaseButton>
      <BaseButton type="submit" form="transaction-form" :loading="loading">
        {{ item ? 'Enregistrer' : 'Créer' }}
      </BaseButton>
    </template>
  </SidePanel>

  <ConfirmDialog
    v-model:open="deleteDialog"
    title="Supprimer cette écriture ?"
    confirm-label="Supprimer"
    danger
    @confirm="remove"
  >
    <p>Son justificatif sera supprimé aussi. Cette action est irréversible.</p>
  </ConfirmDialog>
</template>

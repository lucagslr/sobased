<script setup lang="ts">
/** One transaction in a list: date, label, category, status, signed amount. */
import { Paperclip, Repeat } from 'lucide-vue-next'

import type { Transaction } from '@/api/finance'
import ColorDot from '@/components/ui/ColorDot.vue'
import { signedChf } from '@/utils/money'
import { formatDate } from '@/utils/projects'

import TransactionStatusBadge from './TransactionStatusBadge.vue'

defineProps<{ transaction: Transaction; showProject?: boolean }>()
const emit = defineEmits<{ open: [] }>()
</script>

<template>
  <li class="border-b border-line">
    <button
      type="button"
      class="group flex w-full items-start gap-3 px-1 py-2.5 text-left"
      @click="emit('open')"
    >
      <span class="w-20 shrink-0 pt-0.5 text-sm text-muted tabular-nums">
        {{ formatDate(transaction.date) }}
      </span>
      <span class="min-w-0 flex-1">
        <span class="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span class="font-medium group-hover:underline">{{ transaction.label }}</span>
          <TransactionStatusBadge :status="transaction.display_status" />
          <Repeat
            v-if="transaction.recurring_expense"
            class="size-3.5 text-muted"
            aria-label="Frais récurrent"
          />
          <Paperclip
            v-if="transaction.has_receipt"
            class="size-3.5 text-muted"
            aria-label="Justificatif joint"
          />
        </span>
        <span class="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          <span v-if="showProject" class="inline-flex items-center gap-1.5">
            <ColorDot :color="transaction.project_color" /> {{ transaction.project_name }}
          </span>
          <span>{{ transaction.category_name }}</span>
          <span v-if="transaction.vendor || transaction.contact_name">
            {{ transaction.vendor || transaction.contact_name }}
          </span>
          <span v-if="transaction.payer">Avancé par {{ transaction.payer.name }}</span>
        </span>
      </span>
      <span
        class="shrink-0 pt-0.5 text-sm font-semibold tabular-nums"
        :class="transaction.kind === 'income' ? 'text-fg' : 'text-muted'"
      >
        {{ signedChf(transaction.amount, transaction.kind) }}
      </span>
    </button>
  </li>
</template>

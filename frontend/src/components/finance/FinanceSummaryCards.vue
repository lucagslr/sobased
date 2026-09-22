<script setup lang="ts">
/** Income, expenses, balance, and what still needs attention. */
import type { FinanceSummary } from '@/api/finance'
import { chf } from '@/utils/money'

defineProps<{ summary: FinanceSummary }>()
</script>

<template>
  <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
    <div class="rounded-2xl border border-line p-4">
      <p class="text-xs font-medium text-muted">Recettes</p>
      <p class="mt-1 text-lg font-semibold tabular-nums">{{ chf(summary.income) }}</p>
    </div>
    <div class="rounded-2xl border border-line p-4">
      <p class="text-xs font-medium text-muted">Dépenses</p>
      <p class="mt-1 text-lg font-semibold tabular-nums">{{ chf(summary.expense) }}</p>
    </div>
    <div class="rounded-2xl border border-line p-4">
      <p class="text-xs font-medium text-muted">Solde</p>
      <p
        class="mt-1 text-lg font-semibold tabular-nums"
        :class="Number(summary.balance) < 0 ? 'text-danger' : ''"
      >
        {{ chf(summary.balance) }}
      </p>
    </div>
    <div
      class="rounded-2xl border p-4"
      :class="summary.needs_receipt || summary.to_pay.count ? 'border-danger' : 'border-line'"
    >
      <p class="text-xs font-medium text-muted">À traiter</p>
      <p class="mt-1 text-sm">
        <span :class="summary.needs_receipt ? 'font-semibold text-danger' : 'text-muted'">
          {{ summary.needs_receipt }} à justifier
        </span>
        <br />
        <span :class="summary.to_pay.count ? 'font-semibold text-warning' : 'text-muted'">
          {{ summary.to_pay.count }} à payer · {{ chf(summary.to_pay.total) }}
        </span>
        <br />
        <span class="text-muted">
          {{ summary.to_reimburse.count }} à rembourser · {{ chf(summary.to_reimburse.total) }}
        </span>
      </p>
    </div>
  </div>
</template>

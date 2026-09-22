<script setup lang="ts">
/** Totals per category (or per project): a compact table. */
import { chf } from '@/utils/money'

defineProps<{
  title: string
  rows: { key: string | number; name: string; expense: string; income: string; balance: string }[]
}>()
</script>

<template>
  <section class="rounded-2xl border border-line p-4">
    <h2 class="mb-2 text-sm font-semibold">{{ title }}</h2>
    <p v-if="!rows.length" class="text-sm text-muted">Rien sur cette période.</p>
    <table v-else class="w-full text-sm">
      <thead class="text-xs text-muted">
        <tr>
          <th class="pb-1 text-left font-medium">&nbsp;</th>
          <th class="pb-1 text-right font-medium">Dépenses</th>
          <th class="pb-1 text-right font-medium">Recettes</th>
          <th class="hidden pb-1 text-right font-medium sm:table-cell">Solde</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.key" class="border-t border-line">
          <td class="py-1.5 pr-2">{{ row.name }}</td>
          <td class="py-1.5 text-right tabular-nums text-muted">{{ chf(row.expense) }}</td>
          <td class="py-1.5 text-right tabular-nums">{{ chf(row.income) }}</td>
          <td
            class="hidden py-1.5 text-right font-medium tabular-nums sm:table-cell"
            :class="Number(row.balance) < 0 ? 'text-danger' : ''"
          >
            {{ chf(row.balance) }}
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

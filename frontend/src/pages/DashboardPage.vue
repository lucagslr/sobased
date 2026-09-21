<script setup lang="ts">
/** Placeholder until phase 4 (widgets, saved views, overdue modal). */
import { LayoutDashboard } from 'lucide-vue-next'
import { computed } from 'vue'

import EmptyState from '@/components/ui/EmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const firstName = computed(() => auth.user?.first_name || auth.user?.username || '')
const today = new Intl.DateTimeFormat('fr-CH', { dateStyle: 'full' }).format(new Date())
</script>

<template>
  <PageHeader :title="`Salut ${firstName}`" :subtitle="today" />
  <EmptyState
    :icon="LayoutDashboard"
    title="Ton dashboard arrive"
    text="En retard, aujourd'hui, todo épinglées, RDV à venir : les widgets s'afficheront ici dès que les projets et les tâches existeront."
  />
</template>

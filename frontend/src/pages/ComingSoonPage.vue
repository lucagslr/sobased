<script setup lang="ts">
/** Generic placeholder for sections built in a later phase (see route meta). */
import { Hammer } from 'lucide-vue-next'
import { useRoute } from 'vue-router'

import EmptyState from '@/components/ui/EmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'

const route = useRoute()
</script>

<template>
  <PageHeader :title="route.meta.title" />
  <EmptyState
    :icon="Hammer"
    title="En construction"
    :text="`Cette section arrive avec la phase ${route.meta.phase} du développement.`"
  />
</template>

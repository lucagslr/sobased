<script setup lang="ts">
/** Global view of the share links of every project I edit (SPEC §10). */
import { Link2 } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

import { type ShareLink, type ShareState, sharingApi } from '@/api/sharing'
import ShareLinksTable from '@/components/sharing/ShareLinksTable.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { sortLinks, STATE_META, STATE_ORDER } from '@/utils/sharing'

const links = ref<ShareLink[] | null>(null)
const state = ref<ShareState | ''>('')

const stateOptions = [
  { value: '', label: 'Tous les états' },
  ...STATE_ORDER.map((value) => ({ value, label: STATE_META[value].label })),
]

async function load() {
  links.value = sortLinks(await sharingApi.list({ state: state.value }))
}
watch(state, load, { immediate: true })

const activeCount = computed(() => links.value?.filter((l) => l.state === 'active').length ?? 0)
</script>

<template>
  <PageHeader
    title="Liens partagés"
    :subtitle="
      links
        ? `${activeCount} lien${activeCount > 1 ? 's' : ''} actif${activeCount > 1 ? 's' : ''}`
        : ''
    "
  >
    <BaseSelect v-model="state" label="État" :options="stateOptions" class="w-44" />
  </PageHeader>

  <div v-if="links === null" class="space-y-2">
    <SkeletonBlock v-for="n in 4" :key="n" class="h-14" />
  </div>
  <EmptyState
    v-else-if="!links.length"
    :icon="Link2"
    title="Aucun lien partagé"
    text="Depuis un fichier ou l'onglet Liens d'un projet : « Partager par lien » crée une page sans compte, avec mot de passe, expiration, filigrane et journal d'accès."
  />
  <ShareLinksTable v-else :links="links" show-project @changed="load" />
</template>

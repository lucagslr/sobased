<script setup lang="ts">
/** "Liens" tab of a project: its share links, and new ones from its files. */
import { Link2, Plus } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

import type { Project } from '@/api/projects'
import { type ShareLink, sharingApi } from '@/api/sharing'
import ShareLinkPanel from '@/components/sharing/ShareLinkPanel.vue'
import ShareLinksTable from '@/components/sharing/ShareLinksTable.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSwitch from '@/components/ui/BaseSwitch.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { atLeast } from '@/utils/roles'
import { sortLinks } from '@/utils/sharing'

const props = defineProps<{ project: Project }>()

const links = ref<ShareLink[] | null>(null)
const includeDescendants = ref(false)
const panel = ref(false)

const canEdit = computed(() => atLeast(props.project.my_role, 'editor'))

async function load() {
  links.value = sortLinks(
    await sharingApi.list({
      project: props.project.id,
      include_descendants: includeDescendants.value || undefined,
    }),
  )
}
watch([() => props.project.id, includeDescendants], load, { immediate: true })
</script>

<template>
  <div v-if="!canEdit" class="text-sm text-muted">
    Les liens partagés sont gérés par les éditeurs du projet.
  </div>
  <template v-else>
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <BaseButton @click="panel = true">
        <Plus class="size-4" aria-hidden="true" /> Nouveau lien
      </BaseButton>
      <BaseSwitch
        v-if="project.depth < 4"
        v-model="includeDescendants"
        label="Avec les sous-projets"
        class="ml-auto"
      />
    </div>

    <div v-if="links === null" class="space-y-2">
      <SkeletonBlock v-for="n in 3" :key="n" class="h-14" />
    </div>
    <EmptyState
      v-else-if="!links.length"
      :icon="Link2"
      title="Aucun lien partagé"
      text="Un lien ouvre un fichier (ou une sélection) sur une page sans compte : mot de passe, expiration, quotas, filigrane, journal d'accès."
    />
    <ShareLinksTable v-else :links="links" @changed="load" />

    <ShareLinkPanel v-model:open="panel" :target="{ projectId: project.id }" @saved="load" />
  </template>
</template>

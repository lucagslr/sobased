<script setup lang="ts">
/**
 * "Fichiers" tab of a project: its assets (and those of the sub-projects on
 * request), filtered by kind and status, searchable; upload of a new one
 * for editors. Each row opens the asset page.
 */
import { FolderOpen, Plus, Search } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { type Asset, type AssetKind, type AssetStatus, filesApi } from '@/api/files'
import type { Project } from '@/api/projects'
import AssetRow from '@/components/files/AssetRow.vue'
import UploadPanel from '@/components/files/UploadPanel.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import BaseSwitch from '@/components/ui/BaseSwitch.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useAuthStore } from '@/stores/auth'
import { KIND_LABELS, KIND_ORDER, STATUS_META, STATUS_ORDER } from '@/utils/files'
import { atLeast } from '@/utils/roles'

const props = defineProps<{ project: Project }>()

const router = useRouter()
const auth = useAuthStore()

const assets = ref<Asset[] | null>(null)
const kind = ref<AssetKind | ''>('')
const status = ref<AssetStatus | ''>('')
const search = ref('')
const includeDescendants = ref(false)
const uploadPanel = ref(false)

const canEdit = computed(() => atLeast(props.project.my_role, 'editor'))
const kindOptions = [
  { value: '', label: 'Tous les types' },
  ...KIND_ORDER.map((value) => ({ value, label: KIND_LABELS[value] })),
]
const statusOptions = [
  { value: '', label: 'Tous les statuts' },
  ...STATUS_ORDER.map((value) => ({ value, label: STATUS_META[value].label })),
]

let debounce: ReturnType<typeof setTimeout> | null = null
async function load() {
  assets.value = await filesApi.list({
    project: props.project.id,
    include_descendants: includeDescendants.value || undefined,
    kind: kind.value,
    status: status.value,
    search: search.value.trim() || undefined,
  })
}
watch([() => props.project.id, kind, status, includeDescendants], load, { immediate: true })
watch(search, () => {
  if (debounce) clearTimeout(debounce)
  debounce = setTimeout(load, 250)
})

const filtered = computed(() => kind.value || status.value || search.value.trim())
</script>

<template>
  <div class="mb-4 flex flex-wrap items-end gap-2">
    <BaseButton v-if="canEdit" @click="uploadPanel = true">
      <Plus class="size-4" aria-hidden="true" /> Nouveau fichier
    </BaseButton>
    <label class="relative ml-auto w-full sm:w-56">
      <span class="sr-only">Rechercher un fichier</span>
      <Search
        class="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted"
        aria-hidden="true"
      />
      <input
        v-model="search"
        type="search"
        placeholder="Rechercher…"
        class="h-10 w-full rounded-lg border border-line bg-surface pr-3 pl-9 text-sm placeholder:text-muted"
      />
    </label>
    <BaseSelect v-model="kind" label="Type" :options="kindOptions" class="w-full sm:w-40" />
    <BaseSelect v-model="status" label="Statut" :options="statusOptions" class="w-full sm:w-40" />
    <BaseSwitch
      v-if="project.depth < 4"
      v-model="includeDescendants"
      label="Avec les sous-projets"
      class="w-full sm:w-auto"
    />
  </div>

  <div v-if="assets === null" class="space-y-2">
    <SkeletonBlock v-for="n in 4" :key="n" class="h-16" />
  </div>

  <EmptyState
    v-else-if="!assets.length"
    :icon="FolderOpen"
    :title="filtered ? 'Aucun fichier ne correspond' : 'Aucun fichier'"
    :text="
      filtered
        ? 'Élargis les filtres, ou cherche autrement.'
        : canEdit
          ? 'Mix, cover, clip, dossier de presse : dépose ici les fichiers du projet, avec leurs versions et les retours de l\'équipe.'
          : 'Personne n\'a encore déposé de fichier dans ce projet.'
    "
  />

  <ul v-else class="divide-y divide-line rounded-xl border border-line bg-surface px-1">
    <AssetRow v-for="asset in assets" :key="asset.id" :asset="asset" />
  </ul>

  <UploadPanel
    v-model:open="uploadPanel"
    :project-id="project.id"
    :max-upload-mb="auth.user?.max_upload_mb"
    @created="router.push(`/projets/${project.id}/fichiers/${$event.id}`)"
  />
</template>

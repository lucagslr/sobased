<script setup lang="ts">
/**
 * One asset in the "Fichiers" tab: thumbnail (or kind icon), name, latest
 * version, status, open threads. The whole row opens the asset page.
 */
import { MessageSquare } from 'lucide-vue-next'
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import type { Asset } from '@/api/files'
import { formatSize, versionLabel } from '@/utils/files'
import { formatDate } from '@/utils/projects'

import AssetKindIcon from './AssetKindIcon.vue'
import AssetStatusBadge from './AssetStatusBadge.vue'

const props = defineProps<{ asset: Asset }>()

const latest = computed(() => props.asset.latest_version)
const thumbnail = computed(() => latest.value?.derivatives.thumbnail_url ?? null)
</script>

<template>
  <li>
    <RouterLink
      :to="`/projets/${asset.project}/fichiers/${asset.id}`"
      class="flex items-center gap-3 rounded-xl px-2 py-2.5 hover:bg-surface-2"
    >
      <span
        class="flex size-12 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-surface-2 text-muted"
      >
        <img
          v-if="thumbnail"
          :src="thumbnail"
          alt=""
          class="size-full object-cover"
          loading="lazy"
        />
        <AssetKindIcon v-else :kind="asset.kind" class="size-5" />
      </span>
      <span class="min-w-0 flex-1">
        <span class="block truncate text-sm font-medium">{{ asset.name }}</span>
        <span class="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted">
          <template v-if="latest">
            <span>{{ versionLabel(latest.number, latest.label) }}</span>
            <span aria-hidden="true">·</span>
            <span>{{ formatSize(latest.size_bytes) }}</span>
            <span aria-hidden="true">·</span>
            <span>{{ formatDate(latest.created_at) }}</span>
            <span v-if="latest.open_threads" class="inline-flex items-center gap-1">
              <span aria-hidden="true">·</span>
              <MessageSquare class="size-3" aria-hidden="true" />
              {{ latest.open_threads }}
              <span class="sr-only">fils ouverts</span>
            </span>
          </template>
        </span>
      </span>
      <AssetStatusBadge :status="asset.status" class="shrink-0" />
    </RouterLink>
  </li>
</template>

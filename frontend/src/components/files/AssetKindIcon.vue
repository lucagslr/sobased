<script setup lang="ts">
/** One icon per kind of asset, used in lists and empty viewers. */
import { File, FileText, Image, Music, Video } from 'lucide-vue-next'
import { computed } from 'vue'

import type { AssetKind } from '@/api/files'
import { KIND_LABELS } from '@/utils/files'

const props = defineProps<{ kind: AssetKind }>()

const ICONS = { audio: Music, image: Image, video: Video, document: FileText, other: File }
const icon = computed(() => ICONS[props.kind])
</script>

<template>
  <component :is="icon" :aria-label="KIND_LABELS[kind]" role="img" />
</template>

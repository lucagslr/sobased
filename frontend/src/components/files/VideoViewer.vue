<script setup lang="ts">
/**
 * Video player: the browser's own <video> on the original file (MP4/WebM
 * play everywhere; a ProRes .mov will not, and the download stays). Comment
 * markers are drawn on a thin timeline under the player, at their timestamp.
 */
import { computed, ref, watch } from 'vue'

import type { AssetVersion } from '@/api/files'
import type { Thread } from '@/utils/files'

const props = defineProps<{
  version: AssetVersion
  threads: Thread[]
  selectedId: number | null
  initialTime: number
}>()
const emit = defineEmits<{ select: [id: number]; time: [seconds: number] }>()

const video = ref<HTMLVideoElement | null>(null)
const duration = ref((props.version.duration_ms ?? 0) / 1000)
const currentTime = ref(props.initialTime)

const markers = computed(() =>
  duration.value
    ? props.threads
        .filter((thread) => thread.root.timestamp_ms !== null)
        .map((thread) => ({
          id: thread.root.id,
          left: Math.min(100, (thread.root.timestamp_ms! / 1000 / duration.value) * 100),
          resolved: thread.root.is_resolved,
          body: thread.root.body,
        }))
    : [],
)

function onLoaded() {
  if (!video.value) return
  duration.value = video.value.duration || duration.value
  if (props.initialTime > 0) video.value.currentTime = props.initialTime
}

function onTime() {
  if (!video.value) return
  currentTime.value = video.value.currentTime
  emit('time', currentTime.value)
}

function seekTo(seconds: number) {
  if (!video.value) return
  video.value.currentTime = seconds
  currentTime.value = seconds
  emit('time', seconds)
}

watch(
  () => props.version.id,
  () => {
    duration.value = (props.version.duration_ms ?? 0) / 1000
  },
)

defineExpose({ seekTo })
</script>

<template>
  <div class="rounded-xl bg-surface-2 p-2">
    <video
      ref="video"
      :src="version.file_url ?? ''"
      :poster="version.derivatives.thumbnail_url ?? undefined"
      controls
      preload="metadata"
      playsinline
      class="mx-auto block max-h-[70vh] w-full rounded-lg bg-black"
      @loadedmetadata="onLoaded"
      @timeupdate="onTime"
    />
    <div
      v-if="markers.length"
      class="relative mx-3 mt-3 mb-1 h-4"
      aria-label="Repères des commentaires"
    >
      <div class="absolute inset-x-0 top-1/2 h-0.5 -translate-y-1/2 rounded bg-line" />
      <button
        v-for="marker in markers"
        :key="marker.id"
        type="button"
        class="absolute top-0 flex h-4 w-4 -translate-x-1/2 items-center justify-center rounded-full text-[10px] leading-none"
        :class="
          marker.id === selectedId
            ? 'bg-warning text-white'
            : marker.resolved
              ? 'bg-line text-muted'
              : 'bg-fg text-surface'
        "
        :style="{ left: `${marker.left}%` }"
        :title="marker.body"
        :aria-label="`Commentaire : ${marker.body.slice(0, 60)}`"
        @click="emit('select', marker.id)"
      >
        ●
      </button>
    </div>
  </div>
</template>

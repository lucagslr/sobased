<script setup lang="ts">
/**
 * Audio player on wavesurfer (SPEC §9). The waveform comes from the peaks
 * computed by the server: nothing is decoded in the browser, a 50 MB WAV
 * shows up at once. Playback uses the MP3 stream when it is ready, the
 * original otherwise. Comment markers sit above the waveform at their
 * timestamp; clicking one selects the thread. The current time is emitted
 * so that the page can keep it when switching version.
 */
import { Pause, Play } from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import WaveSurfer from 'wavesurfer.js'

import type { AssetVersion } from '@/api/files'
import BaseButton from '@/components/ui/BaseButton.vue'
import { formatTimestamp, type Thread } from '@/utils/files'

const props = defineProps<{
  version: AssetVersion
  threads: Thread[]
  selectedId: number | null
  /** Seconds to start from (position kept from the previous version). */
  initialTime: number
}>()
const emit = defineEmits<{ select: [id: number]; time: [seconds: number] }>()

const container = ref<HTMLElement | null>(null)
const playing = ref(false)
const currentTime = ref(props.initialTime)
const duration = ref((props.version.duration_ms ?? 0) / 1000)
const ready = ref(false)
const failed = ref('')
let wave: WaveSurfer | null = null

const source = computed(() => props.version.derivatives.stream_url ?? props.version.file_url ?? '')
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

function colours() {
  const styles = getComputedStyle(document.documentElement)
  return {
    wave: styles.getPropertyValue('--c-muted').trim() || '#78716c',
    progress: styles.getPropertyValue('--c-fg').trim() || '#1c1917',
  }
}

async function build() {
  wave?.destroy()
  ready.value = false
  failed.value = ''
  if (!container.value || !source.value) return
  let peaks: number[][] | undefined
  const peaksUrl = props.version.derivatives.peaks_url
  if (peaksUrl) {
    try {
      const response = await fetch(peaksUrl, { credentials: 'same-origin' })
      const data = (await response.json()) as { points: number[]; duration_ms: number }
      peaks = [data.points]
      if (!duration.value && data.duration_ms) duration.value = data.duration_ms / 1000
    } catch {
      peaks = undefined // the waveform is then decoded in the browser
    }
  }
  const { wave: waveColor, progress: progressColor } = colours()
  wave = WaveSurfer.create({
    container: container.value,
    url: source.value,
    peaks,
    duration: duration.value || undefined,
    waveColor,
    progressColor,
    cursorColor: progressColor,
    height: 96,
    barWidth: 2,
    barGap: 1,
    barRadius: 1,
    normalize: true,
    dragToSeek: true,
  })
  wave.on('ready', (seconds) => {
    ready.value = true
    if (seconds) duration.value = seconds
    if (props.initialTime > 0)
      wave?.setTime(Math.min(props.initialTime, seconds || props.initialTime))
  })
  wave.on('timeupdate', (seconds) => {
    currentTime.value = seconds
    emit('time', seconds)
  })
  wave.on('play', () => (playing.value = true))
  wave.on('pause', () => (playing.value = false))
  wave.on('finish', () => (playing.value = false))
  wave.on('error', (error) => {
    failed.value = `Lecture impossible (${String(error)}).`
  })
}

onMounted(build)
watch(() => props.version.id, build)
onBeforeUnmount(() => wave?.destroy())

function toggle() {
  wave?.playPause()
}

function seekTo(seconds: number) {
  wave?.setTime(seconds)
  currentTime.value = seconds
  emit('time', seconds)
}

defineExpose({ seekTo })
</script>

<template>
  <div class="rounded-xl bg-surface-2 p-4">
    <div class="relative pt-4">
      <button
        v-for="marker in markers"
        :key="marker.id"
        type="button"
        class="absolute top-0 z-10 flex h-4 w-4 -translate-x-1/2 items-center justify-center rounded-full text-[10px] leading-none"
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
      <div ref="container" class="min-h-24" />
    </div>
    <div class="mt-3 flex items-center gap-3">
      <BaseButton
        variant="secondary"
        size="sm"
        :disabled="!ready"
        :aria-label="playing ? 'Pause' : 'Lecture'"
        @click="toggle"
      >
        <Pause v-if="playing" class="size-4" aria-hidden="true" />
        <Play v-else class="size-4" aria-hidden="true" />
      </BaseButton>
      <span class="text-sm tabular-nums text-muted">
        {{ formatTimestamp(currentTime * 1000) }} / {{ formatTimestamp(duration * 1000) }}
      </span>
      <span v-if="!ready && !failed" class="text-xs text-muted">Chargement…</span>
      <span v-if="failed" class="text-xs text-danger">{{ failed }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * The public audio player: wavesurfer on the server's peaks, the stream
 * (watermarked or not) as source, no download control anywhere. Several
 * tracks make a playlist with previous / next and autoplay of the next one.
 */
import { Pause, Play, SkipBack, SkipForward } from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import WaveSurfer from 'wavesurfer.js'

import type { PublicItem } from '@/api/sharing'
import BaseButton from '@/components/ui/BaseButton.vue'
import { formatTimestamp } from '@/utils/files'

const props = defineProps<{ tracks: PublicItem[] }>()
const emit = defineEmits<{ blocked: [] }>()

const container = ref<HTMLElement | null>(null)
const index = ref(0)
const playing = ref(false)
const ready = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const failed = ref('')
let wave: WaveSurfer | null = null
let autoplay = false

const track = computed(() => props.tracks[index.value])

function colours() {
  const styles = getComputedStyle(document.documentElement)
  return {
    wave: styles.getPropertyValue('--c-muted').trim() || '#78716c',
    progress: styles.getPropertyValue('--c-fg').trim() || '#1c1917',
  }
}

async function build() {
  wave?.destroy()
  wave = null
  ready.value = false
  failed.value = ''
  playing.value = false
  currentTime.value = 0
  duration.value = (track.value?.duration_ms ?? 0) / 1000
  if (!container.value || !track.value?.media_url) return
  let peaks: number[][] | undefined
  if (track.value.peaks_url) {
    try {
      const response = await fetch(track.value.peaks_url, { credentials: 'same-origin' })
      const data = (await response.json()) as { points: number[]; duration_ms: number }
      peaks = [data.points]
      if (!duration.value && data.duration_ms) duration.value = data.duration_ms / 1000
    } catch {
      peaks = undefined
    }
  }
  const { wave: waveColor, progress: progressColor } = colours()
  wave = WaveSurfer.create({
    container: container.value,
    url: track.value.media_url,
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
    if (autoplay) {
      autoplay = false
      wave?.play()
    }
  })
  wave.on('timeupdate', (seconds) => (currentTime.value = seconds))
  wave.on('play', () => (playing.value = true))
  wave.on('pause', () => (playing.value = false))
  wave.on('finish', () => {
    playing.value = false
    if (index.value < props.tracks.length - 1) {
      autoplay = true
      index.value += 1
    }
  })
  wave.on('error', (error) => {
    // 410 from the stream: quota reached while listening.
    failed.value = 'Lecture impossible.'
    if (String(error).includes('410')) emit('blocked')
  })
}

onMounted(build)
watch(index, build)
watch(
  () => props.tracks.map((t) => t.media_url).join('|'),
  () => build(),
)
onBeforeUnmount(() => wave?.destroy())

function toggle() {
  wave?.playPause()
}

function select(position: number) {
  if (position === index.value) {
    toggle()
    return
  }
  autoplay = true
  index.value = position
}
</script>

<template>
  <div class="rounded-2xl border border-line bg-surface p-4 sm:p-6">
    <p class="truncate text-lg font-semibold">{{ track?.name }}</p>
    <p v-if="track?.label" class="text-sm text-muted">{{ track.label }}</p>
    <div ref="container" class="mt-4 min-h-24" />
    <div class="mt-3 flex items-center gap-2">
      <BaseButton
        v-if="tracks.length > 1"
        variant="ghost"
        size="sm"
        :disabled="index === 0"
        aria-label="Piste précédente"
        @click="select(index - 1)"
      >
        <SkipBack class="size-4" aria-hidden="true" />
      </BaseButton>
      <BaseButton
        variant="secondary"
        :disabled="!ready"
        :aria-label="playing ? 'Pause' : 'Lecture'"
        @click="toggle"
      >
        <Pause v-if="playing" class="size-5" aria-hidden="true" />
        <Play v-else class="size-5" aria-hidden="true" />
      </BaseButton>
      <BaseButton
        v-if="tracks.length > 1"
        variant="ghost"
        size="sm"
        :disabled="index >= tracks.length - 1"
        aria-label="Piste suivante"
        @click="select(index + 1)"
      >
        <SkipForward class="size-4" aria-hidden="true" />
      </BaseButton>
      <span class="ml-1 text-sm tabular-nums text-muted">
        {{ formatTimestamp(currentTime * 1000) }} / {{ formatTimestamp(duration * 1000) }}
      </span>
      <span v-if="!ready && !failed && track?.media_url" class="text-xs text-muted"
        >Chargement…</span
      >
      <span v-if="failed" class="text-xs text-danger">{{ failed }}</span>
    </div>

    <ol v-if="tracks.length > 1" class="mt-5 divide-y divide-line border-t border-line">
      <li v-for="(item, position) in tracks" :key="item.version_id">
        <button
          type="button"
          class="flex w-full items-center gap-3 py-2.5 text-left text-sm"
          :class="position === index ? 'font-semibold' : 'text-fg/80 hover:text-fg'"
          @click="select(position)"
        >
          <span class="w-5 shrink-0 text-xs text-muted tabular-nums">{{ position + 1 }}</span>
          <span class="min-w-0 flex-1 truncate">
            {{ item.name }}<span v-if="item.label" class="text-muted"> · {{ item.label }}</span>
          </span>
          <span v-if="!item.ready" class="text-xs text-muted">préparation…</span>
          <span v-else-if="item.duration_ms" class="text-xs tabular-nums text-muted">
            {{ formatTimestamp(item.duration_ms) }}
          </span>
        </button>
      </li>
    </ol>
  </div>
</template>

<script setup lang="ts">
/**
 * PDF viewer on pdf.js (SPEC §9, comments per page). Pages are rendered into
 * canvases only when they come into view (a 200-page dossier stays light),
 * at the container's width and the screen's pixel density. The page most
 * visible is reported so that a new comment is anchored on it; each page
 * carries the count of its threads.
 *
 * The worker is a same-origin module (Vite serves it): the CSP keeps
 * `worker-src 'self' blob:` and `script-src 'self'`. pdf.js 6 needs no eval.
 */
import * as pdfjs from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { AssetVersion } from '@/api/files'
import type { Thread } from '@/utils/files'

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl

const props = defineProps<{
  version: AssetVersion
  threads: Thread[]
  selectedId: number | null
}>()
const emit = defineEmits<{ page: [page: number]; select: [id: number] }>()

const root = ref<HTMLElement | null>(null)
const pageCount = ref(0)
const ratio = ref(1.4142) // A4 until the first page tells
const failed = ref('')
const rendered = new Set<number>()
let doc: pdfjs.PDFDocumentProxy | null = null
let observer: IntersectionObserver | null = null
let visibility: IntersectionObserver | null = null
const visibleRatios = new Map<number, number>()

const threadsByPage = computed(() => {
  const map = new Map<number, Thread[]>()
  for (const thread of props.threads) {
    if (thread.root.page === null) continue
    map.set(thread.root.page, [...(map.get(thread.root.page) ?? []), thread])
  }
  return map
})

function pageElements(): HTMLElement[] {
  return root.value ? Array.from(root.value.querySelectorAll<HTMLElement>('[data-page]')) : []
}

async function renderPage(number: number) {
  if (!doc || rendered.has(number)) return
  rendered.add(number)
  const holder = pageElements()[number - 1]
  if (!holder) return
  const page = await doc.getPage(number)
  const base = page.getViewport({ scale: 1 })
  const width = holder.clientWidth
  const dpr = window.devicePixelRatio || 1
  const viewport = page.getViewport({ scale: (width / base.width) * dpr })
  const canvas = document.createElement('canvas')
  canvas.width = Math.floor(viewport.width)
  canvas.height = Math.floor(viewport.height)
  canvas.style.width = `${width}px`
  canvas.style.height = `${Math.floor(viewport.height / dpr)}px`
  canvas.setAttribute('role', 'img')
  canvas.setAttribute('aria-label', `Page ${number}`)
  await page.render({ canvas, viewport }).promise
  holder.replaceChildren(canvas)
  holder.style.aspectRatio = ''
}

function observe() {
  observer?.disconnect()
  visibility?.disconnect()
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) renderPage(Number((entry.target as HTMLElement).dataset.page))
      }
    },
    { rootMargin: '600px 0px' },
  )
  visibility = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        visibleRatios.set(
          Number((entry.target as HTMLElement).dataset.page),
          entry.intersectionRatio,
        )
      }
      let best = 0
      let bestRatio = 0
      for (const [page, value] of visibleRatios) {
        if (value > bestRatio) {
          best = page
          bestRatio = value
        }
      }
      if (best) emit('page', best)
    },
    { threshold: [0, 0.25, 0.5, 0.75, 1] },
  )
  for (const element of pageElements()) {
    observer.observe(element)
    visibility.observe(element)
  }
}

async function load() {
  failed.value = ''
  pageCount.value = 0
  rendered.clear()
  visibleRatios.clear()
  await doc?.loadingTask.destroy()
  doc = null
  if (!props.version.file_url) return
  try {
    doc = await pdfjs.getDocument({ url: props.version.file_url, withCredentials: true }).promise
    const first = await doc.getPage(1)
    const viewport = first.getViewport({ scale: 1 })
    ratio.value = viewport.height / viewport.width
    pageCount.value = doc.numPages
    await nextTick()
    observe()
    emit('page', 1)
  } catch (error) {
    failed.value = `Ce PDF ne s'ouvre pas (${(error as Error).message}).`
  }
}

onMounted(load)
watch(() => props.version.id, load)
onBeforeUnmount(() => {
  observer?.disconnect()
  visibility?.disconnect()
  doc?.loadingTask.destroy()
})

function scrollToPage(page: number) {
  pageElements()[page - 1]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

defineExpose({ scrollToPage })
</script>

<template>
  <div class="rounded-xl bg-surface-2 p-2 sm:p-4">
    <p v-if="failed" class="p-4 text-sm text-danger">{{ failed }}</p>
    <p v-else-if="!pageCount" class="p-4 text-sm text-muted">Ouverture du PDF…</p>
    <div ref="root" class="mx-auto max-w-3xl space-y-4">
      <div v-for="page in pageCount" :key="page" class="relative">
        <div
          class="overflow-hidden rounded-md bg-white shadow-sm"
          :data-page="page"
          :style="{ aspectRatio: `1 / ${ratio}` }"
        />
        <div class="mt-1 flex items-center justify-between px-1 text-xs text-muted">
          <span>Page {{ page }} / {{ pageCount }}</span>
          <button
            v-if="threadsByPage.get(page)?.length"
            type="button"
            class="rounded-full px-2 py-0.5 font-medium"
            :class="
              threadsByPage.get(page)!.some((t) => t.root.id === selectedId)
                ? 'bg-warning-soft text-warning'
                : 'bg-surface text-fg'
            "
            @click="emit('select', threadsByPage.get(page)![0].root.id)"
          >
            {{ threadsByPage.get(page)!.length }}
            {{ threadsByPage.get(page)!.length > 1 ? 'commentaires' : 'commentaire' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

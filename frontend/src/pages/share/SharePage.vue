<script setup lang="ts">
/**
 * The public share page (/s/:token, SPEC §10): no account. Four states:
 * loading, gone (404 / 410), password gate, content. Content by kind:
 * audio tracks in one player, images (watermarked server-side), videos,
 * PDFs, and a download card for the rest. While a watermarked stream is
 * being prepared the page polls every 3 s.
 */
import { Download, Lock, Unlink } from 'lucide-vue-next'
import { computed, defineAsyncComponent, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ApiError } from '@/api/client'
import { type PublicItem, type PublicShare, sharingApi } from '@/api/sharing'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import FormError from '@/components/ui/FormError.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { formatTimestamp } from '@/utils/files'

const PublicPlayer = defineAsyncComponent(() => import('@/components/sharing/PublicPlayer.vue'))
const PdfViewer = defineAsyncComponent(() => import('@/components/files/PdfViewer.vue'))

const route = useRoute()
const token = computed(() => String(route.params.token))

const share = ref<PublicShare | null>(null)
const status = ref<'loading' | 'ok' | 'gone' | 'missing'>('loading')
const password = ref('')
const unlocking = ref(false)
const gateError = ref('')
let pollTimer: ReturnType<typeof setTimeout> | null = null

const tracks = computed(() => share.value?.items.filter((i) => i.kind === 'audio') ?? [])
const others = computed(() => share.value?.items.filter((i) => i.kind !== 'audio') ?? [])
const preparing = computed(() => share.value?.items.some((i) => !i.ready && !i.error) ?? false)

async function load() {
  if (pollTimer) clearTimeout(pollTimer)
  try {
    share.value = await sharingApi.open(token.value)
    status.value = 'ok'
    document.title = `${share.value.title} · SOBASED`
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) status.value = 'missing'
    else if (error instanceof ApiError && error.status === 410) status.value = 'gone'
    else throw error
  }
  // A watermark still cooking (Celery): ask again until every item is ready.
  if (preparing.value) pollTimer = setTimeout(load, 3000)
}
watch(token, load, { immediate: true })
onBeforeUnmount(() => {
  if (pollTimer) clearTimeout(pollTimer)
})

async function unlock() {
  unlocking.value = true
  gateError.value = ''
  try {
    share.value = await sharingApi.unlock(token.value, password.value)
    password.value = ''
  } catch (error) {
    if (error instanceof ApiError && error.status === 410) status.value = 'gone'
    else gateError.value = error instanceof ApiError ? error.message : 'Réessaie.'
  } finally {
    unlocking.value = false
  }
}

function sizeOf(item: PublicItem): string {
  return item.duration_ms ? formatTimestamp(item.duration_ms) : ''
}
</script>

<template>
  <div v-if="status === 'loading'" class="space-y-4 pt-6">
    <SkeletonBlock class="h-8 w-64" />
    <SkeletonBlock class="h-40 w-full" />
  </div>

  <div v-else-if="status === 'missing' || status === 'gone'" class="py-20 text-center">
    <Unlink class="mx-auto size-8 text-muted" aria-hidden="true" />
    <h1 class="mt-4 text-xl font-semibold">
      {{ status === 'gone' ? "Ce lien n'est plus disponible" : "Ce lien n'existe pas" }}
    </h1>
    <p class="mt-2 text-sm text-muted">
      {{
        status === 'gone'
          ? 'Il a expiré, a été révoqué, ou son quota est atteint. Demande un nouveau lien à la personne qui te l’a envoyé.'
          : 'Vérifie l’adresse : elle a peut-être été tronquée en la copiant.'
      }}
    </p>
  </div>

  <template v-else-if="share">
    <h1 class="pt-2 text-2xl font-semibold tracking-tight">{{ share.title }}</h1>

    <form
      v-if="share.requires_password"
      class="mt-6 max-w-sm space-y-4 rounded-2xl border border-line bg-surface p-5"
      @submit.prevent="unlock"
    >
      <p class="flex items-center gap-2 text-sm text-muted">
        <Lock class="size-4" aria-hidden="true" /> Ce partage est protégé par un mot de passe.
      </p>
      <BaseInput
        v-model="password"
        type="password"
        label="Mot de passe"
        autocomplete="off"
        required
      />
      <FormError :message="gateError" />
      <BaseButton type="submit" block :loading="unlocking" :disabled="!password">Ouvrir</BaseButton>
    </form>

    <div v-else class="mt-5 space-y-6">
      <p v-if="preparing" class="text-sm text-muted">Préparation de l'écoute…</p>

      <PublicPlayer
        v-if="tracks.some((t) => t.ready)"
        :tracks="tracks"
        @blocked="status = 'gone'"
      />

      <section v-for="item in others" :key="item.version_id" class="space-y-2">
        <h2 v-if="share.items.length > 1" class="text-base font-semibold">
          {{ item.name
          }}<span v-if="item.label" class="font-normal text-muted"> · {{ item.label }}</span>
        </h2>
        <div
          v-if="item.kind === 'image' && item.media_url"
          class="overflow-hidden rounded-2xl border border-line bg-surface-2"
        >
          <img
            :src="item.media_url"
            :alt="item.name"
            class="mx-auto block max-h-[80vh] max-w-full"
            draggable="false"
            @contextmenu.prevent
          />
        </div>
        <video
          v-else-if="item.kind === 'video' && item.media_url"
          :src="item.media_url"
          :poster="item.thumbnail_url ?? undefined"
          controls
          controlslist="nodownload noremoteplayback"
          disablepictureinpicture
          playsinline
          preload="metadata"
          class="w-full rounded-2xl bg-black"
          @contextmenu.prevent
        />
        <PdfViewer
          v-else-if="
            item.kind === 'document' && item.mime_type === 'application/pdf' && item.media_url
          "
          :src="item.media_url"
        />
        <div
          v-else
          class="rounded-2xl border border-line bg-surface p-6 text-center text-sm text-muted"
        >
          {{ item.name }} · {{ item.mime_type || 'fichier' }}
          <span v-if="sizeOf(item)"> · {{ sizeOf(item) }}</span>
          <p v-if="!item.download_url" class="mt-1">Pas d'aperçu pour ce type de fichier.</p>
        </div>
        <p v-if="item.error" class="text-sm text-danger">
          Préparation impossible : {{ item.error }}
        </p>
        <a
          v-if="item.download_url"
          :href="item.download_url"
          class="inline-flex h-9 items-center gap-2 rounded-lg border border-line bg-surface px-3 text-sm font-medium hover:bg-surface-2"
        >
          <Download class="size-4" aria-hidden="true" /> Télécharger {{ item.name }}
        </a>
      </section>

      <div v-if="share.allow_download && tracks.length" class="flex flex-wrap gap-2">
        <a
          v-for="item in tracks.filter((t) => t.download_url)"
          :key="item.version_id"
          :href="item.download_url ?? ''"
          class="inline-flex h-9 items-center gap-2 rounded-lg border border-line bg-surface px-3 text-sm font-medium hover:bg-surface-2"
        >
          <Download class="size-4" aria-hidden="true" /> Télécharger {{ item.name }}
        </a>
      </div>
    </div>
  </template>
</template>

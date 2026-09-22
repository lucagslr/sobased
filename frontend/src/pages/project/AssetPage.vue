<script setup lang="ts">
/**
 * One asset (SPEC §9): its versions, the viewer of the chosen version (image
 * with areas, audio waveform, video, PDF pages, or a download card) and the
 * comment column. Switching version keeps the playback position. The anchor
 * of a new comment comes from the viewer: the paused time, the drawn area or
 * the page in view. Rights come from the project's role.
 */
import {
  ArrowLeft,
  Bell,
  BellOff,
  Download,
  Info,
  Link2,
  MoreHorizontal,
  Plus,
  Trash2,
} from 'lucide-vue-next'
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import { type Asset, type AssetComment, type AssetVersion, filesApi } from '@/api/files'
import { type Project, projectsApi } from '@/api/projects'
import AssetKindIcon from '@/components/files/AssetKindIcon.vue'
import AssetStatusBadge from '@/components/files/AssetStatusBadge.vue'
import CommentThreads, { type DraftAnchor } from '@/components/files/CommentThreads.vue'
import ImageViewer from '@/components/files/ImageViewer.vue'
import StatusPanel from '@/components/files/StatusPanel.vue'
import UploadPanel from '@/components/files/UploadPanel.vue'
import VersionPanel from '@/components/files/VersionPanel.vue'
import VideoViewer from '@/components/files/VideoViewer.vue'
import ShareLinkPanel from '@/components/sharing/ShareLinkPanel.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import {
  anchorKind,
  buildThreads,
  formatSize,
  formatTimestamp,
  KIND_LABELS,
  type Rect,
  rectPayload,
  sortThreads,
  versionLabel,
} from '@/utils/files'
import { atLeast } from '@/utils/roles'

// Heavy libraries (wavesurfer, pdf.js) only load with their kind of file.
const AudioViewer = defineAsyncComponent(() => import('@/components/files/AudioViewer.vue'))
const PdfViewer = defineAsyncComponent(() => import('@/components/files/PdfViewer.vue'))

const route = useRoute()
const router = useRouter()
const ui = useUiStore()
const auth = useAuthStore()

const project = ref<Project | null>(null)
const asset = ref<Asset | null>(null)
const versions = ref<AssetVersion[]>([])
const currentId = ref<number | null>(null)
const comments = ref<AssetComment[] | null>(null)
const notFound = ref(false)
const selectedId = ref<number | null>(null)

// Anchors proposed by the viewers.
const playbackTime = ref(0)
const draftRect = ref<Rect | null>(null)
const visiblePage = ref<number | null>(null)
const anchorCleared = ref(false)

const statusPanel = ref(false)
const versionPanel = ref(false)
const uploadPanel = ref(false)
const confirmDelete = ref(false)
const deleting = ref(false)
const menu = ref(false)
const sharePanel = ref(false)

const audio = ref<InstanceType<typeof AudioViewer> | null>(null)
const video = ref<InstanceType<typeof VideoViewer> | null>(null)
const pdf = ref<InstanceType<typeof PdfViewer> | null>(null)

const assetId = computed(() => Number(route.params.assetId))
const projectId = computed(() => Number(route.params.id))
const current = computed(() => versions.value.find((v) => v.id === currentId.value) ?? null)
const role = computed(() => project.value?.my_role ?? null)
const canComment = computed(() => atLeast(role.value, 'commenter'))
const canEdit = computed(() => atLeast(role.value, 'editor'))
const isAdmin = computed(() => atLeast(role.value, 'admin'))
// The viewer follows the version's real kind (a PNG sent as v2 of a video).
const viewKind = computed(() => current.value?.kind ?? asset.value?.kind ?? 'other')
const kind = computed(() => anchorKind(viewKind.value))
const threads = computed(() => sortThreads(buildThreads(comments.value ?? []), kind.value))
const pending = computed(() => current.value?.derivatives.pending ?? false)

const draftAnchor = computed<DraftAnchor | null>(() => {
  if (anchorCleared.value) return null
  if (kind.value === 'time') {
    const ms = Math.round(playbackTime.value * 1000)
    return { label: `à ${formatTimestamp(ms)}`, payload: { timestamp_ms: ms } }
  }
  if (kind.value === 'rect') {
    return draftRect.value
      ? { label: 'zone dessinée', payload: rectPayload(draftRect.value) }
      : null
  }
  if (kind.value === 'page' && visiblePage.value) {
    return { label: `page ${visiblePage.value}`, payload: { page: visiblePage.value } }
  }
  return null
})

async function load() {
  notFound.value = false
  asset.value = null
  try {
    const [loadedProject, loadedAsset] = await Promise.all([
      projectsApi.get(projectId.value),
      filesApi.get(assetId.value),
    ])
    if (loadedProject.is_shell || loadedAsset.project !== projectId.value) {
      notFound.value = true
      return
    }
    project.value = loadedProject as Project
    asset.value = loadedAsset
    document.title = `${loadedAsset.name} · SOBASED`
    versions.value = await filesApi.versions(assetId.value)
    const wanted = Number(route.query.v)
    currentId.value =
      versions.value.find((v) => v.number === wanted)?.id ?? versions.value[0]?.id ?? null
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound.value = true
    else throw error
  }
}
watch(assetId, load, { immediate: true })

async function loadComments() {
  if (!currentId.value) return
  comments.value = await filesApi.comments(currentId.value)
}
watch(currentId, async (id) => {
  comments.value = null
  selectedId.value = null
  draftRect.value = null
  anchorCleared.value = false
  if (id) {
    await router.replace({ query: { ...route.query, v: current.value?.number } })
    await loadComments()
  }
})

// Processing runs in Celery: poll a little while the derivatives are pending.
let pollTimer: ReturnType<typeof setTimeout> | null = null
watch(
  pending,
  (value) => {
    if (pollTimer) clearTimeout(pollTimer)
    if (!value) return
    pollTimer = setTimeout(async () => {
      if (!currentId.value) return
      const fresh = await filesApi.version(currentId.value)
      versions.value = versions.value.map((v) => (v.id === fresh.id ? fresh : v))
    }, 3000)
  },
  { immediate: true },
)

function switchVersion(version: AssetVersion) {
  currentId.value = version.id // the viewers read playbackTime as initialTime
}

function select(id: number) {
  selectedId.value = id
  const thread = threads.value.find((t) => t.root.id === id)
  if (!thread) return
  if (thread.root.timestamp_ms !== null) {
    const seconds = thread.root.timestamp_ms / 1000
    audio.value?.seekTo(seconds)
    video.value?.seekTo(seconds)
  }
  if (thread.root.page !== null) pdf.value?.scrollToPage(thread.root.page)
}

function onCreated(comment: AssetComment) {
  comments.value = [...(comments.value ?? []), comment]
  draftRect.value = null
  if (comment.parent === null) selectedId.value = comment.id
  refreshVersionCounts()
}

async function refreshVersionCounts() {
  if (!currentId.value) return
  const fresh = await filesApi.version(currentId.value)
  versions.value = versions.value.map((v) => (v.id === fresh.id ? fresh : v))
}

async function onChanged() {
  await loadComments()
  refreshVersionCounts()
}

async function toggleFollow() {
  if (!asset.value) return
  try {
    asset.value = asset.value.is_following
      ? await filesApi.unfollow(asset.value.id)
      : await filesApi.follow(asset.value.id)
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'Le suivi est resté tel quel.', 'error')
  }
}

async function onVersioned(version: AssetVersion) {
  versions.value = [version, ...versions.value]
  asset.value = await filesApi.get(assetId.value)
  currentId.value = version.id
}

function onVersionSaved(version: AssetVersion) {
  versions.value = versions.value.map((v) => (v.id === version.id ? version : v))
}

async function onVersionDeleted(id: number) {
  versions.value = versions.value.filter((v) => v.id !== id)
  if (currentId.value === id) currentId.value = versions.value[0]?.id ?? null
  asset.value = await filesApi.get(assetId.value)
}

async function removeAsset() {
  if (!asset.value) return
  deleting.value = true
  try {
    await filesApi.remove(asset.value.id)
    ui.toast('Fichier supprimé', 'success')
    router.push(`/projets/${projectId.value}/fichiers`)
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'La suppression a échoué.', 'error')
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <div v-if="notFound" class="py-16 text-center">
    <h1 class="text-xl font-semibold">Fichier introuvable</h1>
    <p class="mt-2 text-sm text-muted">Il a été supprimé, ou tu n'y as pas accès.</p>
    <RouterLink
      :to="`/projets/${projectId}/fichiers`"
      class="mt-4 inline-block font-medium underline"
    >
      Retour aux fichiers
    </RouterLink>
  </div>

  <div v-else-if="!asset || !project" class="space-y-4">
    <SkeletonBlock class="h-5 w-48" />
    <SkeletonBlock class="h-9 w-72" />
    <SkeletonBlock class="h-72 w-full" />
  </div>

  <template v-else>
    <nav
      class="mb-3 flex flex-wrap items-center gap-1.5 text-sm text-muted"
      aria-label="Fil d'Ariane"
    >
      <RouterLink
        :to="`/projets/${project.id}/fichiers`"
        class="inline-flex items-center gap-1 hover:text-fg"
      >
        <ArrowLeft class="size-4" aria-hidden="true" /> {{ project.name }} · Fichiers
      </RouterLink>
    </nav>

    <header class="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <h1 class="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <AssetKindIcon :kind="asset.kind" class="size-6 shrink-0 text-muted" />
          <span class="truncate">{{ asset.name }}</span>
        </h1>
        <div class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm text-muted">
          <button type="button" class="inline-flex" @click="statusPanel = true">
            <AssetStatusBadge :status="asset.status" />
          </button>
          <span>{{ KIND_LABELS[asset.kind] }}</span>
          <span v-if="current">{{ formatSize(current.size_bytes) }}</span>
          <span v-if="pending" class="text-xs">Traitement en cours…</span>
        </div>
      </div>
      <div class="flex flex-wrap gap-2">
        <BaseButton variant="secondary" size="sm" @click="toggleFollow">
          <BellOff v-if="asset.is_following" class="size-4" aria-hidden="true" />
          <Bell v-else class="size-4" aria-hidden="true" />
          {{ asset.is_following ? 'Ne plus suivre' : 'Suivre' }}
        </BaseButton>
        <BaseButton v-if="canEdit" variant="secondary" size="sm" @click="statusPanel = true">
          Changer le statut
        </BaseButton>
        <BaseButton v-if="canEdit" size="sm" @click="uploadPanel = true">
          <Plus class="size-4" aria-hidden="true" /> Nouvelle version
        </BaseButton>
        <div class="relative">
          <BaseButton
            variant="secondary"
            size="sm"
            aria-label="Plus d'actions"
            @click="menu = !menu"
          >
            <MoreHorizontal class="size-4" aria-hidden="true" />
          </BaseButton>
          <div
            v-if="menu"
            class="absolute right-0 z-20 mt-1 w-56 overflow-hidden rounded-xl border border-line bg-surface py-1 shadow-lg"
            @click="menu = false"
          >
            <a
              v-if="current?.file_url"
              :href="filesApi.downloadUrl(current)"
              class="flex items-center gap-2 px-3 py-2 text-sm hover:bg-surface-2"
            >
              <Download class="size-4" aria-hidden="true" /> Télécharger l'original
            </a>
            <button
              type="button"
              class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-surface-2"
              @click="versionPanel = true"
            >
              <Info class="size-4" aria-hidden="true" /> Détails de la version
            </button>
            <button
              v-if="canEdit"
              type="button"
              class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-surface-2"
              @click="sharePanel = true"
            >
              <Link2 class="size-4" aria-hidden="true" /> Partager par lien
            </button>
            <button
              v-if="canEdit"
              type="button"
              class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-danger hover:bg-surface-2"
              @click="confirmDelete = true"
            >
              <Trash2 class="size-4" aria-hidden="true" /> Supprimer le fichier
            </button>
          </div>
        </div>
      </div>
    </header>

    <div
      v-if="versions.length > 1"
      class="no-scrollbar -mx-4 mb-4 flex gap-1.5 overflow-x-auto px-4 sm:mx-0 sm:px-0"
      role="tablist"
      aria-label="Versions"
    >
      <button
        v-for="version in versions"
        :key="version.id"
        type="button"
        role="tab"
        :aria-selected="version.id === currentId"
        class="shrink-0 rounded-full border px-3 py-1 text-sm transition-colors"
        :class="
          version.id === currentId
            ? 'border-fg bg-fg text-surface'
            : 'border-line text-muted hover:text-fg'
        "
        @click="switchVersion(version)"
      >
        {{ versionLabel(version.number, version.label) }}
        <span v-if="version.open_threads" class="ml-1 text-xs opacity-80"
          >· {{ version.open_threads }}</span
        >
      </button>
    </div>

    <div v-if="current" class="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
      <div class="min-w-0">
        <ImageViewer
          v-if="viewKind === 'image'"
          :version="current"
          :threads="threads"
          :selected-id="selectedId"
          :draft="draftRect"
          :can-draw="canComment"
          @select="select"
          @draw="
            (rect) => {
              draftRect = rect
              anchorCleared = false
            }
          "
        />
        <AudioViewer
          v-else-if="viewKind === 'audio'"
          ref="audio"
          :key="current.id"
          :version="current"
          :threads="threads"
          :selected-id="selectedId"
          :initial-time="playbackTime"
          @select="select"
          @time="playbackTime = $event"
        />
        <VideoViewer
          v-else-if="viewKind === 'video'"
          ref="video"
          :key="current.id"
          :version="current"
          :threads="threads"
          :selected-id="selectedId"
          :initial-time="playbackTime"
          @select="select"
          @time="playbackTime = $event"
        />
        <PdfViewer
          v-else-if="viewKind === 'document'"
          ref="pdf"
          :key="current.id"
          :src="current.file_url ?? ''"
          :threads="threads"
          :selected-id="selectedId"
          @select="select"
          @page="visiblePage = $event"
        />
        <div v-else class="rounded-xl bg-surface-2 p-8 text-center">
          <AssetKindIcon :kind="asset.kind" class="mx-auto size-10 text-muted" />
          <p class="mt-3 text-sm font-medium">{{ current.original_filename }}</p>
          <p class="mt-1 text-xs text-muted">
            {{ current.mime_type || 'Type inconnu' }} · {{ formatSize(current.size_bytes) }} · pas
            d'aperçu pour ce type
          </p>
          <a
            v-if="current.file_url"
            :href="filesApi.downloadUrl(current)"
            class="mt-4 inline-flex h-8 items-center gap-2 rounded-lg border border-line bg-surface px-3 text-sm font-medium hover:bg-surface-2"
          >
            <Download class="size-4" aria-hidden="true" /> Télécharger
          </a>
        </div>

        <p v-if="current.note" class="mt-3 text-sm whitespace-pre-line text-muted">
          <span class="font-medium text-fg">{{ versionLabel(current.number, current.label) }}</span>
          — {{ current.note }}
        </p>
      </div>

      <CommentThreads
        :version-id="current.id"
        :threads="threads"
        :anchor-kind="kind"
        :draft-anchor="draftAnchor"
        :selected-id="selectedId"
        :can-comment="canComment"
        :can-resolve="canEdit"
        :is-admin="isAdmin"
        :loading="comments === null"
        class="lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:self-start"
        @select="select"
        @created="onCreated"
        @changed="onChanged"
        @clear-anchor="anchorCleared = true"
      />
    </div>

    <StatusPanel
      v-model:open="statusPanel"
      :asset="asset"
      :can-change="canEdit"
      @changed="asset = $event"
    />
    <VersionPanel
      v-if="current"
      v-model:open="versionPanel"
      :version="current"
      :can-edit="canEdit"
      :is-last="versions.length === 1"
      @saved="onVersionSaved"
      @deleted="onVersionDeleted"
    />
    <ShareLinkPanel
      v-if="current"
      v-model:open="sharePanel"
      :target="{
        asset,
        versionId: current.id,
        versionLabel: versionLabel(current.number, current.label),
      }"
    />
    <UploadPanel
      v-model:open="uploadPanel"
      :asset="asset"
      :max-upload-mb="auth.user?.max_upload_mb"
      @versioned="onVersioned"
    />
    <ConfirmDialog
      v-model:open="confirmDelete"
      :title="`Supprimer « ${asset.name} » ?`"
      confirm-label="Supprimer"
      danger
      :loading="deleting"
      @confirm="removeAsset"
    >
      Toutes les versions, leurs commentaires et l'historique des statuts disparaissent.
    </ConfirmDialog>
  </template>
</template>

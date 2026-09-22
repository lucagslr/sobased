<script setup lang="ts">
/**
 * The comment column of a version: threads sorted by their anchor (time,
 * page, position), replies, resolve / reopen, edit and delete of one's own
 * comments, and the form for a new thread whose anchor is decided by the
 * viewer (current time, drawn area, visible page) and shown as a chip.
 */
import { Check, MessageSquare, Pencil, RotateCcw, Trash2, X } from 'lucide-vue-next'
import { computed, nextTick, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { type AssetComment, type CommentPayload, filesApi } from '@/api/files'
import MarkdownView from '@/components/tasks/MarkdownView.vue'
import AppAvatar from '@/components/ui/AppAvatar.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { useUiStore } from '@/stores/ui'
import { type AnchorKind, formatTimestamp, type Thread } from '@/utils/files'

export interface DraftAnchor {
  label: string
  payload: Partial<CommentPayload>
}

const props = defineProps<{
  versionId: number
  threads: Thread[]
  anchorKind: AnchorKind
  /** The anchor the viewer proposes for a new thread, or null for none. */
  draftAnchor: DraftAnchor | null
  selectedId: number | null
  canComment: boolean
  canResolve: boolean
  isAdmin: boolean
  loading: boolean
}>()
const emit = defineEmits<{
  select: [id: number]
  created: [comment: AssetComment]
  changed: []
  clearAnchor: []
}>()

const ui = useUiStore()
const draft = ref('')
const sending = ref(false)
const hideResolved = ref(false)
const replyTo = ref<number | null>(null)
const replyDraft = ref('')
const editing = ref<number | null>(null)
const editDraft = ref('')
const list = ref<HTMLElement | null>(null)

const shown = computed(() =>
  hideResolved.value ? props.threads.filter((t) => !t.root.is_resolved) : props.threads,
)
const resolvedCount = computed(() => props.threads.filter((t) => t.root.is_resolved).length)

watch(
  () => props.selectedId,
  async (id) => {
    if (id === null) return
    await nextTick()
    list.value?.querySelector(`[data-thread="${id}"]`)?.scrollIntoView({ block: 'nearest' })
  },
)

function anchorText(comment: AssetComment): string | null {
  if (comment.timestamp_ms !== null) return formatTimestamp(comment.timestamp_ms)
  if (comment.page !== null) return `p. ${comment.page}`
  if (comment.rect_x !== null) return 'zone'
  return null
}

function when(iso: string): string {
  return new Intl.DateTimeFormat('fr-CH', { dateStyle: 'short', timeStyle: 'short' }).format(
    new Date(iso),
  )
}

async function send() {
  const body = draft.value.trim()
  if (!body) return
  sending.value = true
  try {
    const created = await filesApi.addComment(props.versionId, {
      body,
      ...(props.draftAnchor?.payload ?? {}),
    })
    draft.value = ''
    emit('created', created)
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : "Le commentaire n'est pas parti.", 'error')
  } finally {
    sending.value = false
  }
}

async function reply(thread: Thread) {
  const body = replyDraft.value.trim()
  if (!body) return
  sending.value = true
  try {
    const created = await filesApi.addComment(props.versionId, { body, parent: thread.root.id })
    replyDraft.value = ''
    replyTo.value = null
    emit('created', created)
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : "La réponse n'est pas partie.", 'error')
  } finally {
    sending.value = false
  }
}

async function toggleResolved(thread: Thread) {
  try {
    if (thread.root.is_resolved) await filesApi.reopen(thread.root.id)
    else await filesApi.resolve(thread.root.id)
    emit('changed')
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'Le fil est resté tel quel.', 'error')
  }
}

function startEdit(comment: AssetComment) {
  editing.value = comment.id
  editDraft.value = comment.body
}

async function saveEdit(comment: AssetComment) {
  const body = editDraft.value.trim()
  if (!body) return
  try {
    await filesApi.editComment(comment.id, body)
    editing.value = null
    emit('changed')
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'La modification a échoué.', 'error')
  }
}

async function remove(comment: AssetComment) {
  try {
    await filesApi.removeComment(comment.id)
    emit('changed')
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'La suppression a échoué.', 'error')
  }
}
</script>

<template>
  <section class="flex h-full flex-col" aria-label="Commentaires">
    <header class="mb-3 flex items-center justify-between gap-2">
      <h2 class="text-sm font-semibold">
        Commentaires
        <span v-if="threads.length" class="font-normal text-muted">· {{ threads.length }}</span>
      </h2>
      <label v-if="resolvedCount" class="flex items-center gap-1.5 text-xs text-muted">
        <input v-model="hideResolved" type="checkbox" class="size-3.5 accent-fg" />
        Masquer les résolus ({{ resolvedCount }})
      </label>
    </header>

    <form v-if="canComment" class="mb-4" @submit.prevent="send">
      <div class="mb-1.5 flex flex-wrap items-center gap-1.5 text-xs">
        <span
          v-if="draftAnchor"
          class="inline-flex items-center gap-1 rounded-full bg-warning-soft px-2 py-0.5 font-medium text-warning"
        >
          {{ draftAnchor.label }}
          <button
            type="button"
            class="rounded-full hover:bg-black/10"
            aria-label="Commenter sans repère"
            @click="emit('clearAnchor')"
          >
            <X class="size-3" aria-hidden="true" />
          </button>
        </span>
        <span v-else class="text-muted">
          {{
            anchorKind === 'time'
              ? "Mets la lecture en pause à l'endroit voulu, puis commente."
              : anchorKind === 'rect'
                ? "Dessine une zone sur l'image pour y accrocher le commentaire."
                : anchorKind === 'page'
                  ? 'Le commentaire se rattache à la page affichée.'
                  : 'Commentaire général sur cette version.'
          }}
        </span>
      </div>
      <textarea
        v-model="draft"
        rows="2"
        placeholder="Commenter…"
        aria-label="Nouveau commentaire"
        class="w-full rounded-lg border border-line bg-surface px-3 py-2 text-[15px] placeholder:text-muted"
        @keydown.ctrl.enter.prevent="send"
        @keydown.meta.enter.prevent="send"
      />
      <div class="mt-1.5 flex justify-end">
        <BaseButton type="submit" size="sm" :loading="sending" :disabled="!draft.trim()">
          Commenter
        </BaseButton>
      </div>
    </form>

    <p v-if="loading" class="text-sm text-muted">Chargement…</p>
    <div
      v-else-if="!shown.length"
      class="rounded-xl border border-dashed border-line p-4 text-center"
    >
      <MessageSquare class="mx-auto size-5 text-muted" aria-hidden="true" />
      <p class="mt-1 text-sm text-muted">
        {{
          threads.length ? 'Tous les fils sont résolus.' : 'Aucun commentaire sur cette version.'
        }}
      </p>
    </div>

    <ul ref="list" class="min-h-0 flex-1 space-y-2 overflow-y-auto">
      <li
        v-for="(thread, index) in shown"
        :key="thread.root.id"
        :data-thread="thread.root.id"
        class="rounded-xl border p-3 transition-colors"
        :class="[
          thread.root.id === selectedId ? 'border-warning bg-warning-soft/40' : 'border-line',
          thread.root.is_resolved ? 'opacity-70' : '',
        ]"
      >
        <button
          type="button"
          class="flex w-full items-center gap-2 text-left text-xs text-muted"
          @click="emit('select', thread.root.id)"
        >
          <span
            v-if="anchorKind === 'rect' && thread.root.rect_x !== null"
            class="flex size-5 items-center justify-center rounded-full bg-fg text-[11px] font-semibold text-surface"
          >
            {{ threads.filter((t) => t.root.rect_x !== null).indexOf(thread) + 1 }}
          </span>
          <span
            v-else-if="anchorText(thread.root)"
            class="rounded-full bg-surface-2 px-2 py-0.5 font-medium tabular-nums text-fg"
          >
            {{ anchorText(thread.root) }}
          </span>
          <span v-else class="rounded-full bg-surface-2 px-2 py-0.5">général</span>
          <span v-if="thread.root.is_resolved" class="inline-flex items-center gap-1">
            <Check class="size-3" aria-hidden="true" /> résolu
          </span>
          <span class="ml-auto">#{{ index + 1 }}</span>
        </button>

        <template v-for="comment in [thread.root, ...thread.replies]" :key="comment.id">
          <div class="mt-2 flex gap-2" :class="comment.parent !== null ? 'ml-5' : ''">
            <AppAvatar
              :name="comment.author?.display_name ?? 'Utilisateur supprimé'"
              :src="comment.author?.avatar_url"
              :size="24"
            />
            <div class="min-w-0 flex-1">
              <p class="flex flex-wrap items-baseline gap-x-2 text-xs">
                <span class="font-medium text-fg">
                  {{ comment.author?.display_name ?? 'Utilisateur supprimé' }}
                </span>
                <span class="text-muted">
                  {{ when(comment.created_at)
                  }}<template v-if="comment.edited_at"> · modifié</template>
                </span>
                <span class="ml-auto flex gap-0.5">
                  <button
                    v-if="comment.is_mine && editing !== comment.id"
                    type="button"
                    class="rounded p-1 text-muted hover:text-fg"
                    aria-label="Modifier"
                    @click="startEdit(comment)"
                  >
                    <Pencil class="size-3" aria-hidden="true" />
                  </button>
                  <button
                    v-if="comment.is_mine || isAdmin"
                    type="button"
                    class="rounded p-1 text-muted hover:text-danger"
                    aria-label="Supprimer"
                    @click="remove(comment)"
                  >
                    <Trash2 class="size-3" aria-hidden="true" />
                  </button>
                </span>
              </p>
              <form v-if="editing === comment.id" class="mt-1" @submit.prevent="saveEdit(comment)">
                <textarea
                  v-model="editDraft"
                  rows="2"
                  aria-label="Modifier le commentaire"
                  class="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-sm"
                />
                <div class="mt-1 flex justify-end gap-1">
                  <BaseButton variant="ghost" size="sm" @click="editing = null">Annuler</BaseButton>
                  <BaseButton type="submit" size="sm">Enregistrer</BaseButton>
                </div>
              </form>
              <MarkdownView v-else :source="comment.body" class="mt-0.5 text-sm" />
            </div>
          </div>
        </template>

        <div class="mt-2 flex flex-wrap items-center gap-1">
          <BaseButton
            v-if="canComment && replyTo !== thread.root.id"
            variant="ghost"
            size="sm"
            @click="replyTo = thread.root.id"
          >
            Répondre
          </BaseButton>
          <BaseButton
            v-if="canResolve || (canComment && thread.root.is_mine)"
            variant="ghost"
            size="sm"
            @click="toggleResolved(thread)"
          >
            <template v-if="thread.root.is_resolved">
              <RotateCcw class="size-3.5" aria-hidden="true" /> Rouvrir
            </template>
            <template v-else><Check class="size-3.5" aria-hidden="true" /> Résoudre</template>
          </BaseButton>
        </div>
        <form v-if="replyTo === thread.root.id" class="mt-2" @submit.prevent="reply(thread)">
          <textarea
            v-model="replyDraft"
            rows="2"
            placeholder="Répondre…"
            aria-label="Réponse"
            class="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-sm"
            @keydown.ctrl.enter.prevent="reply(thread)"
            @keydown.meta.enter.prevent="reply(thread)"
          />
          <div class="mt-1 flex justify-end gap-1">
            <BaseButton variant="ghost" size="sm" @click="replyTo = null">Annuler</BaseButton>
            <BaseButton type="submit" size="sm" :loading="sending" :disabled="!replyDraft.trim()">
              Répondre
            </BaseButton>
          </div>
        </form>
      </li>
    </ul>
  </section>
</template>

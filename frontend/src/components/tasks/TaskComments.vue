<script setup lang="ts">
/**
 * Comments of a task, with "@username" autocompletion among the project's
 * members. Mentioned members are notified by the server (not by the front).
 */
import { Trash2 } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import type { PublicUser } from '@/api/auth'
import { ApiError } from '@/api/client'
import { type TaskComment, tasksApi } from '@/api/tasks'
import AppAvatar from '@/components/ui/AppAvatar.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { useUiStore } from '@/stores/ui'

import MarkdownView from './MarkdownView.vue'

const props = defineProps<{
  taskId: number
  members: PublicUser[]
  canComment: boolean
  /** Admins may delete any comment. */
  isAdmin: boolean
}>()
const emit = defineEmits<{ count: [total: number] }>()

const ui = useUiStore()
const comments = ref<TaskComment[] | null>(null)
const draft = ref('')
const sending = ref(false)
const textarea = ref<HTMLTextAreaElement | null>(null)

onMounted(async () => {
  comments.value = await tasksApi.comments(props.taskId)
})

// The "@xyz" being typed just before the caret, if any.
const mentionQuery = ref<string | null>(null)
const suggestions = computed(() => {
  const query = mentionQuery.value
  if (query === null) return []
  return props.members
    .filter(
      (user) =>
        user.username.toLowerCase().startsWith(query) ||
        user.display_name.toLowerCase().includes(query),
    )
    .slice(0, 5)
})

function onInput() {
  const caret = textarea.value?.selectionStart ?? draft.value.length
  const match = /(^|[^\w@.])@([A-Za-z0-9_.-]*)$/.exec(draft.value.slice(0, caret))
  mentionQuery.value = match ? match[2].toLowerCase() : null
}

function complete(user: PublicUser) {
  const caret = textarea.value?.selectionStart ?? draft.value.length
  const before = draft.value.slice(0, caret).replace(/@[A-Za-z0-9_.-]*$/, `@${user.username} `)
  draft.value = before + draft.value.slice(caret)
  mentionQuery.value = null
  textarea.value?.focus()
}

async function send() {
  const body = draft.value.trim()
  if (!body) return
  sending.value = true
  try {
    const created = await tasksApi.addComment(props.taskId, body)
    comments.value = [...(comments.value ?? []), created]
    draft.value = ''
    emit('count', comments.value.length)
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : "Le commentaire n'est pas parti.", 'error')
  } finally {
    sending.value = false
  }
}

async function remove(comment: TaskComment) {
  try {
    await tasksApi.removeComment(comment.id)
    comments.value = (comments.value ?? []).filter((current) => current.id !== comment.id)
    emit('count', comments.value.length)
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'La suppression a échoué.', 'error')
  }
}

function when(iso: string): string {
  return new Intl.DateTimeFormat('fr-CH', { dateStyle: 'short', timeStyle: 'short' }).format(
    new Date(iso),
  )
}
</script>

<template>
  <div>
    <ul v-if="comments?.length" class="mb-4 space-y-4">
      <li v-for="comment in comments" :key="comment.id" class="group flex gap-3">
        <AppAvatar
          :name="comment.author?.display_name ?? 'Utilisateur supprimé'"
          :src="comment.author?.avatar_url"
          :size="28"
        />
        <div class="min-w-0 flex-1">
          <p class="flex flex-wrap items-baseline gap-x-2 text-sm">
            <span class="font-medium">
              {{ comment.author?.display_name ?? 'Utilisateur supprimé' }}
            </span>
            <span class="text-xs text-muted">
              {{ when(comment.created_at) }}<template v-if="comment.edited_at"> · modifié</template>
            </span>
            <button
              v-if="comment.is_mine || isAdmin"
              type="button"
              class="ml-auto rounded p-1 text-muted hover:text-danger sm:opacity-0 sm:group-hover:opacity-100"
              aria-label="Supprimer le commentaire"
              @click="remove(comment)"
            >
              <Trash2 class="size-3.5" aria-hidden="true" />
            </button>
          </p>
          <MarkdownView :source="comment.body" class="mt-0.5" />
        </div>
      </li>
    </ul>
    <p v-else-if="comments" class="mb-3 text-sm text-muted">Aucun commentaire.</p>

    <form v-if="canComment" class="relative" @submit.prevent="send">
      <textarea
        ref="textarea"
        v-model="draft"
        rows="2"
        placeholder="Commenter… @ pour mentionner quelqu'un"
        aria-label="Nouveau commentaire"
        class="w-full rounded-lg border border-line bg-surface px-3 py-2 text-[15px] placeholder:text-muted"
        @input="onInput"
        @keydown.ctrl.enter.prevent="send"
        @keydown.meta.enter.prevent="send"
      />
      <ul
        v-if="suggestions.length"
        class="absolute bottom-full z-10 mb-1 w-64 overflow-hidden rounded-xl border border-line bg-surface shadow-lg"
      >
        <li v-for="user in suggestions" :key="user.username">
          <button
            type="button"
            class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-surface-2"
            @click="complete(user)"
          >
            <AppAvatar :name="user.display_name" :src="user.avatar_url" :size="22" />
            <span class="truncate">{{ user.display_name }}</span>
            <span class="truncate text-xs text-muted">@{{ user.username }}</span>
          </button>
        </li>
      </ul>
      <div class="mt-2 flex justify-end">
        <BaseButton type="submit" size="sm" :loading="sending" :disabled="!draft.trim()">
          Commenter
        </BaseButton>
      </div>
    </form>
  </div>
</template>

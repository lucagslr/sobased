<script setup lang="ts">
/**
 * The links of a project or of everything (SPEC §10): state, who, views and
 * plays, expiry; copy the URL, edit, read the journal, revoke in one click,
 * delete. Cards on phones, a table from `md`.
 */
import { Ban, ClipboardList, Copy, Pencil, Trash2 } from 'lucide-vue-next'
import { ref } from 'vue'
import { RouterLink } from 'vue-router'

import { ApiError } from '@/api/client'
import { type ShareLink, sharingApi } from '@/api/sharing'
import BaseButton from '@/components/ui/BaseButton.vue'
import ColorDot from '@/components/ui/ColorDot.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import { useUiStore } from '@/stores/ui'
import { formatDate } from '@/utils/projects'
import { expiryText, quotaText } from '@/utils/sharing'

import AccessLogPanel from './AccessLogPanel.vue'
import ShareLinkPanel from './ShareLinkPanel.vue'
import ShareStateBadge from './ShareStateBadge.vue'

defineProps<{ links: ShareLink[]; showProject?: boolean }>()
const emit = defineEmits<{ changed: [] }>()

const ui = useUiStore()
const editing = ref<ShareLink | null>(null)
const editPanel = ref(false)
const logFor = ref<ShareLink | null>(null)
const logPanel = ref(false)
const deleting = ref<ShareLink | null>(null)
const confirmDelete = ref(false)
const busy = ref(false)

async function copy(link: ShareLink) {
  if (!link.url) {
    ui.toast('Adresse illisible (clé de chiffrement changée).', 'error')
    return
  }
  try {
    await navigator.clipboard.writeText(link.url)
    ui.toast('Lien copié', 'success')
  } catch {
    ui.toast('Copie impossible dans ce navigateur.', 'error')
  }
}

async function revoke(link: ShareLink) {
  try {
    await sharingApi.revoke(link.id)
    ui.toast('Lien révoqué : la page publique répond désormais « plus disponible ».', 'success')
    emit('changed')
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : "Le lien n'a pas été révoqué.", 'error')
  }
}

async function remove() {
  if (!deleting.value) return
  busy.value = true
  try {
    await sharingApi.remove(deleting.value.id)
    confirmDelete.value = false
    ui.toast('Lien supprimé', 'success')
    emit('changed')
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'La suppression a échoué.', 'error')
  } finally {
    busy.value = false
  }
}

function openEdit(link: ShareLink) {
  editing.value = link
  editPanel.value = true
}
function openLog(link: ShareLink) {
  logFor.value = link
  logPanel.value = true
}
function askDelete(link: ShareLink) {
  deleting.value = link
  confirmDelete.value = true
}
</script>

<template>
  <ul class="space-y-2 md:hidden">
    <li v-for="link in links" :key="link.id" class="rounded-xl border border-line bg-surface p-3">
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0">
          <p class="truncate text-sm font-medium">{{ link.title }}</p>
          <p class="truncate text-xs text-muted">{{ link.target_label }}</p>
        </div>
        <ShareStateBadge :state="link.state" />
      </div>
      <p class="mt-2 flex flex-wrap gap-x-3 text-xs text-muted">
        <span v-if="link.recipient_label">{{ link.recipient_label }}</span>
        <span>{{ quotaText(link.view_count, link.max_views, 'vue') }}</span>
        <span>{{ quotaText(link.play_count, link.max_plays, 'écoute') }}</span>
        <span v-if="link.expires_at">{{ expiryText(link.expires_at) }}</span>
      </p>
      <div class="mt-2 flex flex-wrap gap-1">
        <BaseButton variant="ghost" size="sm" @click="copy(link)"
          ><Copy class="size-4" aria-hidden="true" /> Copier</BaseButton
        >
        <BaseButton variant="ghost" size="sm" @click="openLog(link)"
          ><ClipboardList class="size-4" aria-hidden="true" /> Journal</BaseButton
        >
        <BaseButton variant="ghost" size="sm" @click="openEdit(link)"
          ><Pencil class="size-4" aria-hidden="true" /> Modifier</BaseButton
        >
        <BaseButton v-if="link.state === 'active'" variant="ghost" size="sm" @click="revoke(link)"
          ><Ban class="size-4" aria-hidden="true" /> Révoquer</BaseButton
        >
        <BaseButton v-else variant="ghost" size="sm" class="text-danger" @click="askDelete(link)"
          ><Trash2 class="size-4" aria-hidden="true" /> Supprimer</BaseButton
        >
      </div>
    </li>
  </ul>

  <div class="hidden overflow-x-auto rounded-xl border border-line bg-surface md:block">
    <table class="w-full text-sm">
      <thead class="text-left text-xs text-muted">
        <tr class="border-b border-line">
          <th class="px-3 py-2 font-medium">Lien</th>
          <th v-if="showProject" class="px-3 py-2 font-medium">Projet</th>
          <th class="px-3 py-2 font-medium">Destinataire</th>
          <th class="px-3 py-2 font-medium">État</th>
          <th class="px-3 py-2 font-medium">Vues</th>
          <th class="px-3 py-2 font-medium">Écoutes</th>
          <th class="px-3 py-2 font-medium">Créé</th>
          <th class="px-3 py-2"><span class="sr-only">Actions</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="link in links" :key="link.id" class="border-b border-line last:border-0">
          <td class="max-w-64 px-3 py-2">
            <p class="truncate font-medium">{{ link.title }}</p>
            <p class="truncate text-xs text-muted">{{ link.target_label }}</p>
          </td>
          <td v-if="showProject" class="px-3 py-2">
            <RouterLink
              :to="`/projets/${link.project}/liens`"
              class="inline-flex items-center gap-1.5 hover:underline"
            >
              <ColorDot :color="link.project_color" /> {{ link.project_name }}
            </RouterLink>
          </td>
          <td class="px-3 py-2">{{ link.recipient_label || '—' }}</td>
          <td class="px-3 py-2">
            <ShareStateBadge :state="link.state" />
            <p v-if="link.expires_at && link.state === 'active'" class="mt-0.5 text-xs text-muted">
              {{ expiryText(link.expires_at) }}
            </p>
            <p v-if="link.has_password" class="mt-0.5 text-xs text-muted">mot de passe</p>
          </td>
          <td class="px-3 py-2 tabular-nums">
            {{ quotaText(link.view_count, link.max_views, 'vue') }}
          </td>
          <td class="px-3 py-2 tabular-nums">
            {{ quotaText(link.play_count, link.max_plays, 'écoute') }}
          </td>
          <td class="px-3 py-2 text-muted">{{ formatDate(link.created_at) }}</td>
          <td class="px-1 py-2">
            <div class="flex justify-end gap-0.5">
              <button
                type="button"
                class="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-fg"
                title="Copier le lien"
                aria-label="Copier le lien"
                @click="copy(link)"
              >
                <Copy class="size-4" aria-hidden="true" />
              </button>
              <button
                type="button"
                class="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-fg"
                title="Journal d'accès"
                aria-label="Journal d'accès"
                @click="openLog(link)"
              >
                <ClipboardList class="size-4" aria-hidden="true" />
              </button>
              <button
                type="button"
                class="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-fg"
                title="Modifier"
                aria-label="Modifier"
                @click="openEdit(link)"
              >
                <Pencil class="size-4" aria-hidden="true" />
              </button>
              <button
                v-if="link.state === 'active'"
                type="button"
                class="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-danger"
                title="Révoquer"
                aria-label="Révoquer"
                @click="revoke(link)"
              >
                <Ban class="size-4" aria-hidden="true" />
              </button>
              <button
                v-else
                type="button"
                class="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-danger"
                title="Supprimer"
                aria-label="Supprimer"
                @click="askDelete(link)"
              >
                <Trash2 class="size-4" aria-hidden="true" />
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <ShareLinkPanel v-model:open="editPanel" :link="editing" @saved="emit('changed')" />
  <AccessLogPanel v-model:open="logPanel" :link="logFor" />
  <ConfirmDialog
    v-model:open="confirmDelete"
    title="Supprimer ce lien ?"
    confirm-label="Supprimer"
    danger
    :loading="busy"
    @confirm="remove"
  >
    Le lien et son journal d'accès disparaissent. Un lien encore actif se révoque plutôt.
  </ConfirmDialog>
</template>

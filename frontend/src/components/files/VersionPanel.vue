<script setup lang="ts">
/**
 * Details of one version: technical facts (read-only), label and note
 * (editors), deletion (editors, never the last version).
 */
import { ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { type AssetVersion, filesApi } from '@/api/files'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseTextarea from '@/components/ui/BaseTextarea.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import SidePanel from '@/components/ui/SidePanel.vue'
import { useUiStore } from '@/stores/ui'
import { formatSize, formatTimestamp } from '@/utils/files'

const props = defineProps<{ version: AssetVersion; canEdit: boolean; isLast: boolean }>()
const emit = defineEmits<{ saved: [version: AssetVersion]; deleted: [id: number] }>()
const open = defineModel<boolean>('open', { required: true })

const ui = useUiStore()
const label = ref(props.version.label)
const note = ref(props.version.note)
const saving = ref(false)
const confirmDelete = ref(false)
const deleting = ref(false)

watch(open, (value) => {
  if (!value) return
  label.value = props.version.label
  note.value = props.version.note
})

function when(iso: string): string {
  return new Intl.DateTimeFormat('fr-CH', { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(iso),
  )
}

async function save() {
  saving.value = true
  try {
    const updated = await filesApi.updateVersion(props.version.id, {
      label: label.value.trim(),
      note: note.value.trim(),
    })
    emit('saved', updated)
    open.value = false
  } catch (error) {
    ui.toast(
      error instanceof ApiError ? error.message : "La version n'a pas été modifiée.",
      'error',
    )
  } finally {
    saving.value = false
  }
}

async function remove() {
  deleting.value = true
  try {
    await filesApi.removeVersion(props.version.id)
    confirmDelete.value = false
    open.value = false
    emit('deleted', props.version.id)
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'La suppression a échoué.', 'error')
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <SidePanel
    v-model:open="open"
    :title="`Version ${version.number}`"
    :description="version.original_filename"
  >
    <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
      <dt class="text-muted">Fichier</dt>
      <dd class="truncate">{{ version.original_filename || '—' }}</dd>
      <dt class="text-muted">Type</dt>
      <dd>{{ version.mime_type || '—' }}</dd>
      <dt class="text-muted">Taille</dt>
      <dd>{{ formatSize(version.size_bytes) }}</dd>
      <template v-if="version.width && version.height">
        <dt class="text-muted">Dimensions</dt>
        <dd>{{ version.width }} × {{ version.height }} px</dd>
      </template>
      <template v-if="version.duration_ms">
        <dt class="text-muted">Durée</dt>
        <dd>{{ formatTimestamp(version.duration_ms) }}</dd>
      </template>
      <template v-if="version.page_count">
        <dt class="text-muted">Pages</dt>
        <dd>{{ version.page_count }}</dd>
      </template>
      <dt class="text-muted">Envoyé par</dt>
      <dd>
        {{ version.author?.display_name ?? 'Utilisateur supprimé' }} ·
        {{ when(version.created_at) }}
      </dd>
      <template v-if="version.sha256">
        <dt class="text-muted">SHA-256</dt>
        <dd class="truncate font-mono text-xs" :title="version.sha256">{{ version.sha256 }}</dd>
      </template>
      <template v-if="version.processing_error">
        <dt class="text-muted">Traitement</dt>
        <dd class="text-danger">{{ version.processing_error }}</dd>
      </template>
    </dl>

    <form v-if="canEdit" id="version-form" class="mt-6 space-y-4" @submit.prevent="save">
      <BaseInput v-model="label" label="Libellé" placeholder="mix 2, master, cover finale…" />
      <BaseTextarea
        v-model="note"
        label="Note"
        :rows="4"
        placeholder="Ce qui change dans cette version"
      />
    </form>
    <template v-else>
      <p v-if="version.label" class="mt-6 text-sm">
        <span class="text-muted">Libellé :</span> {{ version.label }}
      </p>
      <p v-if="version.note" class="mt-2 text-sm whitespace-pre-line">{{ version.note }}</p>
    </template>

    <div v-if="canEdit" class="mt-8 border-t border-line pt-4">
      <BaseButton variant="danger" size="sm" :disabled="isLast" @click="confirmDelete = true">
        Supprimer cette version
      </BaseButton>
      <p v-if="isLast" class="mt-1 text-xs text-muted">
        La dernière version ne se supprime pas : supprime le fichier entier.
      </p>
    </div>

    <template v-if="canEdit" #footer>
      <BaseButton variant="secondary" @click="open = false">Annuler</BaseButton>
      <BaseButton type="submit" form="version-form" :loading="saving">Enregistrer</BaseButton>
    </template>
  </SidePanel>

  <ConfirmDialog
    v-model:open="confirmDelete"
    :title="`Supprimer la version ${version.number} ?`"
    confirm-label="Supprimer"
    danger
    :loading="deleting"
    @confirm="remove"
  >
    Le fichier et ses commentaires disparaissent. Les autres versions restent.
  </ConfirmDialog>
</template>

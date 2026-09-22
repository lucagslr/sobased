<script setup lang="ts">
/**
 * Status of an asset: change it (editors, with an optional note) and read
 * its history (who, when, from → to). One panel for both, the history is
 * loaded when it opens.
 */
import { ArrowRight } from 'lucide-vue-next'
import { ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import { type Asset, type AssetStatus, type AssetStatusChange, filesApi } from '@/api/files'
import AppAvatar from '@/components/ui/AppAvatar.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import BaseTextarea from '@/components/ui/BaseTextarea.vue'
import SidePanel from '@/components/ui/SidePanel.vue'
import { useUiStore } from '@/stores/ui'
import { STATUS_META, STATUS_ORDER, statusChangedMessage } from '@/utils/files'

import AssetStatusBadge from './AssetStatusBadge.vue'

const props = defineProps<{ asset: Asset; canChange: boolean }>()
const emit = defineEmits<{ changed: [asset: Asset] }>()
const open = defineModel<boolean>('open', { required: true })

const ui = useUiStore()
const status = ref<AssetStatus>(props.asset.status)
const note = ref('')
const saving = ref(false)
const history = ref<AssetStatusChange[] | null>(null)

const options = STATUS_ORDER.map((value) => ({ value, label: STATUS_META[value].label }))

watch(open, async (value) => {
  if (!value) return
  status.value = props.asset.status
  note.value = ''
  history.value = null
  history.value = await filesApi.statusHistory(props.asset.id)
})

async function save() {
  if (status.value === props.asset.status && !note.value.trim()) {
    open.value = false
    return
  }
  saving.value = true
  try {
    const updated = await filesApi.changeStatus(props.asset.id, status.value, note.value.trim())
    ui.toast(statusChangedMessage(status.value), 'success')
    emit('changed', updated)
    open.value = false
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : "Le statut n'a pas changé.", 'error')
  } finally {
    saving.value = false
  }
}

function when(iso: string): string {
  return new Intl.DateTimeFormat('fr-CH', { dateStyle: 'short', timeStyle: 'short' }).format(
    new Date(iso),
  )
}
</script>

<template>
  <SidePanel v-model:open="open" title="Statut du fichier" :description="asset.name">
    <form v-if="canChange" id="status-form" class="space-y-4" @submit.prevent="save">
      <BaseSelect v-model="status" label="Nouveau statut" :options="options" />
      <BaseTextarea
        v-model="note"
        label="Note"
        :rows="3"
        placeholder="Pourquoi ce changement (facultatif)"
      />
    </form>
    <p v-else class="flex items-center gap-2 text-sm">
      Statut actuel : <AssetStatusBadge :status="asset.status" />
    </p>

    <h3 class="mt-6 mb-2 text-sm font-semibold">Historique</h3>
    <p v-if="history === null" class="text-sm text-muted">Chargement…</p>
    <p v-else-if="!history.length" class="text-sm text-muted">
      Aucun changement : le fichier est resté en brouillon.
    </p>
    <ol v-else class="space-y-3">
      <li v-for="change in history" :key="change.id" class="flex gap-3">
        <AppAvatar
          :name="change.changed_by?.display_name ?? 'Utilisateur supprimé'"
          :src="change.changed_by?.avatar_url"
          :size="28"
        />
        <div class="min-w-0 flex-1 text-sm">
          <p class="flex flex-wrap items-center gap-1.5">
            <AssetStatusBadge :status="change.from_status" />
            <ArrowRight class="size-3.5 text-muted" aria-hidden="true" />
            <AssetStatusBadge :status="change.to_status" />
          </p>
          <p class="mt-0.5 text-xs text-muted">
            {{ change.changed_by?.display_name ?? 'Utilisateur supprimé' }} ·
            {{ when(change.created_at) }}
          </p>
          <p v-if="change.note" class="mt-1 whitespace-pre-line">{{ change.note }}</p>
        </div>
      </li>
    </ol>

    <template v-if="canChange" #footer>
      <BaseButton variant="secondary" @click="open = false">Annuler</BaseButton>
      <BaseButton type="submit" form="status-form" :loading="saving">Enregistrer</BaseButton>
    </template>
  </SidePanel>
</template>

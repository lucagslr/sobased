<script setup lang="ts">
/**
 * "Mes données" (SPEC §16): ask for an export (ZIP built in the background,
 * kept 7 days) and delete the account (password again, irreversible).
 */
import { Download } from 'lucide-vue-next'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import { authApi, type DataExport } from '@/api/auth'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import FormCard from '@/components/ui/FormCard.vue'
import FormError from '@/components/ui/FormError.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { formatDate } from '@/utils/projects'

const auth = useAuthStore()
const ui = useUiStore()
const router = useRouter()

// --- Export ------------------------------------------------------------------------
const exports = ref<DataExport[] | null>(null)
const requesting = ref(false)
const exportError = ref('')
let poll: ReturnType<typeof setInterval> | null = null

const STATUS: Record<DataExport['status'], string> = {
  pending: 'En préparation…',
  ready: 'Prêt',
  failed: 'Échec',
}

async function loadExports() {
  exports.value = await authApi.exports()
  const pending = exports.value.some((item) => item.status === 'pending')
  if (pending && !poll) poll = setInterval(loadExports, 4000)
  if (!pending && poll) {
    clearInterval(poll)
    poll = null
  }
}

async function requestExport() {
  requesting.value = true
  exportError.value = ''
  try {
    await authApi.requestExport()
    await loadExports()
  } catch (error) {
    exportError.value =
      error instanceof ApiError ? error.message : "L'export n'a pas pu être demandé."
  } finally {
    requesting.value = false
  }
}

function size(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}

onMounted(loadExports)
onBeforeUnmount(() => {
  if (poll) clearInterval(poll)
})

// --- Deletion ----------------------------------------------------------------------
const password = ref('')
const confirming = ref(false)
const { loading, error, fieldErrors, submit } = useFormSubmit()

async function deleteAccount() {
  const ok = await submit(() => authApi.deleteAccount(password.value))
  confirming.value = false
  if (!ok) return
  auth.setUser(null)
  ui.toast('Compte supprimé', 'success', 'Tes données personnelles ont été effacées.')
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="space-y-6">
    <FormCard
      title="Exporter mes données"
      description="Un fichier ZIP avec ton profil, tes accès, tes tâches, commentaires, RDV, écritures et les fichiers que tu as déposés. Il est préparé en arrière-plan et reste téléchargeable 7 jours."
    >
      <FormError :message="exportError" />
      <BaseButton :loading="requesting" @click="requestExport">Préparer un export</BaseButton>
      <ul v-if="exports?.length" class="mt-4 divide-y divide-line rounded-xl border border-line">
        <li
          v-for="item in exports"
          :key="item.id"
          class="flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2.5 text-sm"
        >
          <span class="font-medium">Export du {{ formatDate(item.created_at) }}</span>
          <span class="text-muted">
            {{ STATUS[item.status] }}
            <template v-if="item.status === 'ready'"> · {{ size(item.size_bytes) }}</template>
            <template v-if="item.status === 'failed' && item.error"> · {{ item.error }}</template>
          </span>
          <a
            v-if="item.is_available"
            :href="authApi.exportDownloadUrl(item.id)"
            download
            class="ml-auto inline-flex items-center gap-1 font-medium text-fg underline"
          >
            <Download class="size-4" aria-hidden="true" /> Télécharger
          </a>
          <span v-else-if="item.status === 'ready'" class="ml-auto text-muted">Expiré</span>
        </li>
      </ul>
    </FormCard>

    <FormCard
      title="Supprimer mon compte"
      description="Irréversible. Ton nom, ton e-mail, ton avatar, tes connexions Google et Microsoft, tes accès et tes notifications sont effacés. Ce que tu as créé dans les projets partagés reste, signé « Utilisateur supprimé ». Si tu es propriétaire d'un espace ou d'un projet où d'autres personnes travaillent, transfère-le d'abord."
    >
      <form class="max-w-sm space-y-4" @submit.prevent="confirming = true">
        <FormError :message="error" />
        <BaseInput
          v-model="password"
          label="Mot de passe"
          type="password"
          autocomplete="current-password"
          required
          :errors="fieldErrors.password"
        />
        <BaseButton type="submit" variant="danger" :disabled="!password">
          Supprimer mon compte
        </BaseButton>
      </form>
    </FormCard>

    <ConfirmDialog
      v-model:open="confirming"
      title="Supprimer ton compte ?"
      confirm-label="Supprimer définitivement"
      :confirm-name="auth.user?.username"
      danger
      :loading="loading"
      @confirm="deleteAccount"
    >
      <p>Tu seras déconnecté immédiatement et ne pourras plus te reconnecter.</p>
      <p>Pense à télécharger un export de tes données avant.</p>
    </ConfirmDialog>
  </div>
</template>

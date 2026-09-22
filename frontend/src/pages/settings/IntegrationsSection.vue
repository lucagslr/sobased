<script setup lang="ts">
/**
 * Intégrations: the user's Google account (Drive now, Calendar in phase 11)
 * and Microsoft (phase 11). Connecting sends the browser to Google's
 * consent page; Google brings it back to this page with ?google=ok|refus|erreur.
 */
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import { type IntegrationsState, integrationsApi } from '@/api/integrations'
import BaseButton from '@/components/ui/BaseButton.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import FormCard from '@/components/ui/FormCard.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()

const state = ref<IntegrationsState | null>(null)
const busy = ref(false)
const confirmDisconnect = ref(false)

const FEATURE_LABELS: Record<string, string> = { drive: 'Drive', calendar: 'Calendrier' }

async function load() {
  state.value = await integrationsApi.state()
}

onMounted(async () => {
  await load()
  const outcome = route.query.google
  if (outcome === 'ok') ui.toast('Compte Google connecté', 'success')
  else if (outcome === 'refus') ui.toast('Connexion Google refusée ou expirée.', 'error')
  else if (outcome === 'erreur') ui.toast('Google a répondu une erreur. Réessaie.', 'error')
  if (outcome) router.replace({ query: {} })
})

async function connect(features: ('drive' | 'calendar')[]) {
  busy.value = true
  try {
    window.location.href = await integrationsApi.googleConnectUrl(features)
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'Connexion impossible.', 'error')
    busy.value = false
  }
}

async function disconnect() {
  busy.value = true
  try {
    await integrationsApi.googleDisconnect()
    confirmDisconnect.value = false
    ui.toast('Compte Google déconnecté', 'success')
    await load()
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'La déconnexion a échoué.', 'error')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <FormCard
      title="Google"
      description="Drive pour les dossiers de projet et les fichiers attachés ; le calendrier arrive avec la phase 11."
    >
      <SkeletonBlock v-if="!state" class="h-16 w-full" />
      <p v-else-if="!state.google.enabled" class="text-sm text-muted">
        L'intégration Google n'est pas configurée sur ce serveur (variables
        <code>GOOGLE_CLIENT_ID</code> et <code>GOOGLE_CLIENT_SECRET</code>). Tout fonctionne avec le
        stockage interne.
      </p>
      <template v-else-if="state.google.connected">
        <p class="text-sm">
          Connecté comme <span class="font-medium">{{ state.google.email }}</span>
          <span v-if="state.google.features.length" class="text-muted">
            · {{ state.google.features.map((f) => FEATURE_LABELS[f] ?? f).join(', ') }}
          </span>
        </p>
        <p v-if="state.google.status === 'needs_reauth'" class="mt-2 text-sm text-danger">
          Google demande une nouvelle autorisation : reconnecte le compte.
        </p>
        <div class="mt-4 flex flex-wrap gap-2">
          <BaseButton
            v-if="
              !state.google.features.includes('drive') || state.google.status === 'needs_reauth'
            "
            :loading="busy"
            @click="connect(['drive'])"
          >
            {{ state.google.status === 'needs_reauth' ? 'Reconnecter' : 'Autoriser Drive' }}
          </BaseButton>
          <BaseButton variant="secondary" :disabled="busy" @click="confirmDisconnect = true">
            Déconnecter
          </BaseButton>
        </div>
        <p class="mt-3 text-xs text-muted">
          SOBASED n'accède qu'aux fichiers qu'il crée (dossiers de projet, envois) et à ceux que tu
          choisis dans le sélecteur Google. Les jetons sont stockés chiffrés.
        </p>
      </template>
      <template v-else>
        <p class="text-sm text-muted">
          Connecte ton compte Google pour créer un dossier Drive par projet, y envoyer des fichiers
          et attacher des fichiers Drive aux projets, tâches et versions.
        </p>
        <BaseButton class="mt-4" :loading="busy" @click="connect(['drive'])">
          Connecter Google Drive
        </BaseButton>
      </template>
    </FormCard>

    <FormCard title="Microsoft" description="Calendrier Outlook / Teams : phase 11.">
      <p class="text-sm text-muted">
        {{
          state?.microsoft.enabled
            ? 'Bientôt disponible.'
            : "L'intégration Microsoft n'est pas encore configurée sur ce serveur."
        }}
      </p>
    </FormCard>

    <ConfirmDialog
      v-model:open="confirmDisconnect"
      title="Déconnecter Google ?"
      confirm-label="Déconnecter"
      danger
      :loading="busy"
      @confirm="disconnect"
    >
      Les dossiers Drive déjà créés restent accessibles par leur lien, mais SOBASED ne pourra plus
      créer de dossier ni envoyer de fichier avec ce compte.
    </ConfirmDialog>
  </div>
</template>

<script setup lang="ts">
/**
 * Intégrations: the user's Google account (Drive, Calendar) and Microsoft
 * account (Outlook / Teams calendar), then the calendars to display and the
 * target calendar. Connecting sends the browser to the provider's consent
 * page, which brings it back here with ?google=… or ?microsoft=….
 */
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import { type IntegrationsState, integrationsApi } from '@/api/integrations'
import CalendarsCard from '@/components/integrations/CalendarsCard.vue'
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
const confirmMsDisconnect = ref(false)
const calendarsKey = ref(0)

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
  const ms = route.query.microsoft
  if (ms === 'ok') ui.toast('Compte Microsoft connecté', 'success')
  else if (ms === 'refus') ui.toast('Connexion Microsoft refusée ou expirée.', 'error')
  else if (ms === 'erreur') ui.toast('Microsoft a répondu une erreur. Réessaie.', 'error')
  if (outcome || ms) router.replace({ query: {} })
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

async function connectMicrosoft() {
  busy.value = true
  try {
    window.location.href = await integrationsApi.microsoftConnectUrl()
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'Connexion impossible.', 'error')
    busy.value = false
  }
}

async function disconnectMicrosoft() {
  busy.value = true
  try {
    await integrationsApi.microsoftDisconnect()
    confirmMsDisconnect.value = false
    ui.toast('Compte Microsoft déconnecté', 'success')
    await load()
    calendarsKey.value += 1
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'La déconnexion a échoué.', 'error')
  } finally {
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
    calendarsKey.value += 1
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
      description="Drive pour les dossiers de projet et les fichiers attachés, Google Agenda pour la synchronisation."
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
          <BaseButton
            v-if="
              !state.google.features.includes('calendar') && state.google.status !== 'needs_reauth'
            "
            variant="secondary"
            :loading="busy"
            @click="connect(['drive', 'calendar'])"
          >
            Autoriser le calendrier
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

    <FormCard title="Microsoft" description="Calendrier Outlook (les réunions Teams y sont).">
      <SkeletonBlock v-if="!state" class="h-12 w-full" />
      <p v-else-if="!state.microsoft.enabled" class="text-sm text-muted">
        L'intégration Microsoft n'est pas configurée sur ce serveur (variables
        <code>MS_CLIENT_ID</code> et <code>MS_CLIENT_SECRET</code>).
      </p>
      <template v-else-if="state.microsoft.connected">
        <p class="text-sm">
          Connecté comme <span class="font-medium">{{ state.microsoft.email }}</span>
        </p>
        <p v-if="state.microsoft.status === 'needs_reauth'" class="mt-2 text-sm text-danger">
          Microsoft demande une nouvelle autorisation : reconnecte le compte.
        </p>
        <div class="mt-4 flex flex-wrap gap-2">
          <BaseButton
            v-if="state.microsoft.status === 'needs_reauth'"
            :loading="busy"
            @click="connectMicrosoft"
          >
            Reconnecter
          </BaseButton>
          <BaseButton variant="secondary" :disabled="busy" @click="confirmMsDisconnect = true">
            Déconnecter
          </BaseButton>
        </div>
      </template>
      <template v-else>
        <p class="text-sm text-muted">
          Connecte ton compte Microsoft (école, travail) pour voir son calendrier ici et y recevoir
          tes tâches et RDV.
        </p>
        <BaseButton class="mt-4" :loading="busy" @click="connectMicrosoft">
          Connecter Microsoft
        </BaseButton>
      </template>
    </FormCard>

    <CalendarsCard
      v-if="state && (state.google.features.includes('calendar') || state.microsoft.connected)"
      :key="calendarsKey"
    />

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
    <ConfirmDialog
      v-model:open="confirmMsDisconnect"
      title="Déconnecter Microsoft ?"
      confirm-label="Déconnecter"
      danger
      :loading="busy"
      @confirm="disconnectMicrosoft"
    >
      Les calendriers Outlook disparaissent de SOBASED ; les événements déjà créés dans Outlook y
      restent.
    </ConfirmDialog>
  </div>
</template>

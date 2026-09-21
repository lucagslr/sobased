<script setup lang="ts">
/**
 * Notification preferences, saved as soon as a control changes.
 * The e-mails themselves are sent from phase 12; the preferences exist now so
 * the data model does not change later.
 */
import { reactive, watch } from 'vue'

import { authApi } from '@/api/auth'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSwitch from '@/components/ui/BaseSwitch.vue'
import FormCard from '@/components/ui/FormCard.vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const auth = useAuthStore()
const ui = useUiStore()
const user = auth.user!

const prefs = reactive({
  daily_digest_enabled: user.daily_digest_enabled ?? true,
  // The API sends "08:00:00"; <input type="time"> wants "08:00".
  daily_digest_time: (user.daily_digest_time ?? '08:00').slice(0, 5),
  email_on_mention: user.email_on_mention ?? true,
  email_on_assignment: user.email_on_assignment ?? true,
})

watch(prefs, async (value) => {
  if (!value.daily_digest_time) return // field being edited
  try {
    auth.setUser(await authApi.updateMe({ ...value }))
  } catch {
    ui.toast("La préférence n'a pas pu être enregistrée.", 'error')
  }
})
</script>

<template>
  <FormCard
    title="Résumé quotidien"
    description="Un e-mail le matin : en retard, aujourd'hui, RDV du jour, à valider. Rien n'est envoyé si tout est vide."
  >
    <div class="space-y-5">
      <BaseSwitch v-model="prefs.daily_digest_enabled" label="Recevoir le résumé quotidien" />
      <div class="max-w-40">
        <BaseInput
          v-model="prefs.daily_digest_time"
          label="Heure d'envoi"
          type="time"
          :disabled="!prefs.daily_digest_enabled"
          :hint="`Heure locale (${user.timezone})`"
        />
      </div>
    </div>
  </FormCard>

  <FormCard
    title="E-mails"
    description="Les notifications dans l'application restent toujours actives."
  >
    <div class="space-y-5">
      <BaseSwitch
        v-model="prefs.email_on_mention"
        label="Quand on me mentionne"
        description="Un e-mail à chaque @mention dans un commentaire."
      />
      <BaseSwitch
        v-model="prefs.email_on_assignment"
        label="Quand on m'assigne une tâche"
        description="Un e-mail à chaque nouvelle tâche qui m'est assignée."
      />
    </div>
  </FormCard>
</template>

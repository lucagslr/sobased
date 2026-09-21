<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'

import { authApi } from '@/api/auth'
import AuthCard from '@/components/ui/AuthCard.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import FormError from '@/components/ui/FormError.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'

const { loading, error, fieldErrors, submit } = useFormSubmit()
const email = ref('')
const sent = ref(false)

async function onSubmit() {
  sent.value = await submit(() => authApi.requestPasswordReset(email.value))
}
</script>

<template>
  <AuthCard
    title="Mot de passe oublié"
    subtitle="Indique l'e-mail de ton compte : tu recevras un lien pour choisir un nouveau mot de passe."
  >
    <!-- Same message whether the account exists or not (no e-mail enumeration). -->
    <p v-if="sent" class="rounded-lg bg-surface-2 px-4 py-3 text-sm" role="status">
      Si un compte existe pour <strong>{{ email }}</strong
      >, un e-mail vient de partir. Le lien est valable 24 heures.
    </p>
    <form v-else class="space-y-4" @submit.prevent="onSubmit">
      <FormError :message="error" />
      <BaseInput
        v-model="email"
        label="E-mail"
        type="email"
        autocomplete="email"
        required
        :errors="fieldErrors.email"
      />
      <BaseButton type="submit" block :loading="loading">Envoyer le lien</BaseButton>
    </form>
    <template #footer>
      <RouterLink to="/connexion" class="font-medium text-fg underline">
        Retour à la connexion
      </RouterLink>
    </template>
  </AuthCard>
</template>

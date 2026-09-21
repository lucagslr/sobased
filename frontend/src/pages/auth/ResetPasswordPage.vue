<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { authApi } from '@/api/auth'
import AuthCard from '@/components/ui/AuthCard.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import FormError from '@/components/ui/FormError.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()
const { loading, error, fieldErrors, submit } = useFormSubmit()

const password = ref('')
const confirmation = ref('')
const mismatch = ref(false)

async function onSubmit() {
  mismatch.value = password.value !== confirmation.value
  if (mismatch.value) return
  const ok = await submit(() =>
    authApi.confirmPasswordReset(
      String(route.params.uid),
      String(route.params.token),
      password.value,
    ),
  )
  if (!ok) return
  ui.toast('Mot de passe modifié', 'success', 'Tu peux te connecter.')
  router.push({ name: 'login' })
}
</script>

<template>
  <AuthCard title="Nouveau mot de passe">
    <form class="space-y-4" @submit.prevent="onSubmit">
      <FormError :message="error" />
      <BaseInput
        v-model="password"
        label="Nouveau mot de passe"
        type="password"
        autocomplete="new-password"
        hint="10 caractères minimum."
        required
        :errors="fieldErrors.new_password"
      />
      <BaseInput
        v-model="confirmation"
        label="Confirmation"
        type="password"
        autocomplete="new-password"
        required
        :errors="mismatch ? ['Les deux mots de passe ne correspondent pas.'] : undefined"
      />
      <BaseButton type="submit" block :loading="loading">Enregistrer</BaseButton>
    </form>
    <template #footer>
      <RouterLink to="/mot-de-passe-oublie" class="font-medium text-fg underline">
        Demander un nouveau lien
      </RouterLink>
    </template>
  </AuthCard>
</template>

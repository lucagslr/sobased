<script setup lang="ts">
import { reactive, ref } from 'vue'

import { authApi } from '@/api/auth'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import FormCard from '@/components/ui/FormCard.vue'
import FormError from '@/components/ui/FormError.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const { loading, error, fieldErrors, submit } = useFormSubmit()

const form = reactive({ current: '', next: '', confirmation: '' })
const mismatch = ref(false)

async function onSubmit() {
  mismatch.value = form.next !== form.confirmation
  if (mismatch.value) return
  if (!(await submit(() => authApi.changePassword(form.current, form.next)))) return
  Object.assign(form, { current: '', next: '', confirmation: '' })
  ui.toast('Mot de passe modifié', 'success', 'Tes autres appareils ont été déconnectés.')
}
</script>

<template>
  <FormCard
    title="Mot de passe"
    description="Changer de mot de passe déconnecte tes autres appareils."
  >
    <form class="max-w-sm space-y-4" @submit.prevent="onSubmit">
      <FormError :message="error" />
      <BaseInput
        v-model="form.current"
        label="Mot de passe actuel"
        type="password"
        autocomplete="current-password"
        required
        :errors="fieldErrors.current_password"
      />
      <BaseInput
        v-model="form.next"
        label="Nouveau mot de passe"
        type="password"
        autocomplete="new-password"
        hint="10 caractères minimum."
        required
        :errors="fieldErrors.new_password"
      />
      <BaseInput
        v-model="form.confirmation"
        label="Confirmation"
        type="password"
        autocomplete="new-password"
        required
        :errors="mismatch ? ['Les deux mots de passe ne correspondent pas.'] : undefined"
      />
      <BaseButton type="submit" :loading="loading">Changer le mot de passe</BaseButton>
    </form>
  </FormCard>
</template>

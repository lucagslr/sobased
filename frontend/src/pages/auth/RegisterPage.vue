<script setup lang="ts">
import { reactive } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import AuthCard from '@/components/ui/AuthCard.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import FormError from '@/components/ui/FormError.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const auth = useAuthStore()
const ui = useUiStore()
const router = useRouter()
const { loading, error, fieldErrors, submit } = useFormSubmit()

const form = reactive({
  username: '',
  email: '',
  first_name: '',
  last_name: '',
  password: '',
  accept_privacy: false,
})

async function onSubmit() {
  if (!(await submit(() => auth.register({ ...form })))) return
  ui.toast('Compte créé', 'success', 'Un e-mail de confirmation vient de partir.')
  router.push('/')
}
</script>

<template>
  <AuthCard title="Créer un compte" subtitle="Tes espaces, tes projets, tes règles.">
    <form class="space-y-4" @submit.prevent="onSubmit">
      <FormError :message="error" />
      <BaseInput
        v-model="form.username"
        label="Nom d'utilisateur"
        autocomplete="username"
        hint="3 à 30 caractères : lettres, chiffres, point, tiret, underscore. Il ne pourra plus être changé."
        required
        :errors="fieldErrors.username"
      />
      <BaseInput
        v-model="form.email"
        label="E-mail"
        type="email"
        autocomplete="email"
        required
        :errors="fieldErrors.email"
      />
      <div class="grid grid-cols-2 gap-3">
        <BaseInput
          v-model="form.first_name"
          label="Prénom"
          autocomplete="given-name"
          :errors="fieldErrors.first_name"
        />
        <BaseInput
          v-model="form.last_name"
          label="Nom"
          autocomplete="family-name"
          :errors="fieldErrors.last_name"
        />
      </div>
      <BaseInput
        v-model="form.password"
        label="Mot de passe"
        type="password"
        autocomplete="new-password"
        hint="10 caractères minimum."
        required
        :errors="fieldErrors.password"
      />
      <div>
        <label class="flex items-start gap-3 text-sm">
          <input
            v-model="form.accept_privacy"
            type="checkbox"
            required
            class="mt-0.5 size-4 rounded border-line accent-[var(--c-accent)]"
          />
          <span>
            J'ai lu et j'accepte la
            <RouterLink to="/confidentialite" target="_blank" class="font-medium underline">
              politique de confidentialité</RouterLink
            >.
          </span>
        </label>
        <p v-if="fieldErrors.accept_privacy" class="mt-1.5 text-sm text-danger">
          {{ fieldErrors.accept_privacy[0] }}
        </p>
      </div>
      <BaseButton type="submit" block :loading="loading">Créer mon compte</BaseButton>
    </form>
    <template #footer>
      Déjà un compte ?
      <RouterLink to="/connexion" class="font-medium text-fg underline">Se connecter</RouterLink>
    </template>
  </AuthCard>
</template>

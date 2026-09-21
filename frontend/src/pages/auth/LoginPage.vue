<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import AuthCard from '@/components/ui/AuthCard.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import FormError from '@/components/ui/FormError.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { loading, error, fieldErrors, submit } = useFormSubmit()

const username = ref('')
const password = ref('')

async function onSubmit() {
  if (!(await submit(() => auth.login(username.value, password.value)))) return
  // Only follow internal paths: "?suite=https://evil.example" must not work.
  const next = typeof route.query.suite === 'string' ? route.query.suite : '/'
  router.push(next.startsWith('/') && !next.startsWith('//') ? next : '/')
}
</script>

<template>
  <AuthCard title="Connexion" subtitle="Content de te revoir.">
    <form class="space-y-4" @submit.prevent="onSubmit">
      <FormError :message="error" />
      <BaseInput
        v-model="username"
        label="Nom d'utilisateur"
        autocomplete="username"
        required
        :errors="fieldErrors.username"
      />
      <BaseInput
        v-model="password"
        label="Mot de passe"
        type="password"
        autocomplete="current-password"
        required
        :errors="fieldErrors.password"
      />
      <BaseButton type="submit" block :loading="loading">Se connecter</BaseButton>
    </form>
    <template #footer>
      <p>
        <RouterLink to="/mot-de-passe-oublie" class="font-medium text-fg underline">
          Mot de passe oublié ?
        </RouterLink>
      </p>
      <p class="mt-2">
        Pas encore de compte ?
        <RouterLink to="/inscription" class="font-medium text-fg underline">S'inscrire</RouterLink>
      </p>
    </template>
  </AuthCard>
</template>

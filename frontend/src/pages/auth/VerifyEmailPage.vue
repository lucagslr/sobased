<script setup lang="ts">
/** Landing page of the link sent by e-mail: verifies as soon as it opens. */
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { authApi } from '@/api/auth'
import { ApiError } from '@/api/client'
import AuthCard from '@/components/ui/AuthCard.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()
const state = ref<'pending' | 'ok' | 'error'>('pending')
const message = ref('')

onMounted(async () => {
  try {
    await authApi.verifyEmail(String(route.params.token))
    state.value = 'ok'
    // Refresh the profile so the "confirm your e-mail" banner disappears.
    if (auth.isAuthenticated) auth.setUser(await authApi.me())
  } catch (error) {
    state.value = 'error'
    message.value = error instanceof ApiError ? error.message : 'Lien invalide ou expiré.'
  }
})
</script>

<template>
  <AuthCard title="Vérification de l'e-mail">
    <SkeletonBlock v-if="state === 'pending'" class="h-12 w-full" />
    <p v-else-if="state === 'ok'" class="rounded-lg bg-surface-2 px-4 py-3 text-sm" role="status">
      Ton adresse e-mail est confirmée. Tu peux maintenant inviter des personnes et recevoir des
      invitations.
    </p>
    <p v-else class="rounded-lg bg-danger-soft px-4 py-3 text-sm text-danger" role="alert">
      {{ message }} Connecte-toi pour demander un nouveau lien.
    </p>
    <template #footer>
      <RouterLink to="/" class="font-medium text-fg underline">Continuer vers SOBASED</RouterLink>
    </template>
  </AuthCard>
</template>

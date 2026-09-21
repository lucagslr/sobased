<script setup lang="ts">
/** Shown until the e-mail is verified (needed to invite and be invited). */
import { ref } from 'vue'

import { authApi } from '@/api/auth'
import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const auth = useAuthStore()
const ui = useUiStore()
const sending = ref(false)

async function resend() {
  sending.value = true
  try {
    await authApi.resendVerification()
    ui.toast('E-mail envoyé', 'success', `Regarde la boîte ${auth.user?.email}.`)
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : "L'envoi a échoué.", 'error')
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <div
    v-if="auth.user && !auth.user.email_verified"
    class="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 bg-warning-soft px-4 py-2.5 text-sm text-warning"
    role="status"
  >
    <span>Confirme ton adresse e-mail pour pouvoir inviter et être invité.</span>
    <button type="button" class="font-semibold underline" :disabled="sending" @click="resend">
      Renvoyer l'e-mail
    </button>
  </div>
</template>

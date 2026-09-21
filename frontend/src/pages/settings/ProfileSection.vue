<script setup lang="ts">
/** Identity (name, phone, timezone), avatar, and e-mail change. */
import { reactive, ref } from 'vue'

import { authApi } from '@/api/auth'
import { ApiError } from '@/api/client'
import AppAvatar from '@/components/ui/AppAvatar.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import FormCard from '@/components/ui/FormCard.vue'
import FormError from '@/components/ui/FormError.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const auth = useAuthStore()
const ui = useUiStore()
const user = auth.user!

// --- Identity -----------------------------------------------------------------
const profile = reactive({
  first_name: user.first_name ?? '',
  last_name: user.last_name ?? '',
  phone: user.phone ?? '',
  timezone: user.timezone ?? 'Europe/Zurich',
})
const profileForm = useFormSubmit()

// Every IANA timezone known to the browser, e.g. "Europe/Zurich".
const timezones = Intl.supportedValuesOf('timeZone').map((tz) => ({
  value: tz,
  label: tz.replace(/_/g, ' '),
}))

async function saveProfile() {
  const ok = await profileForm.submit(async () => auth.setUser(await authApi.updateMe(profile)))
  if (ok) ui.toast('Profil enregistré', 'success')
}

// --- Avatar ---------------------------------------------------------------------
const fileInput = ref<HTMLInputElement | null>(null)
const avatarBusy = ref(false)

async function onAvatarPicked(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = '' // allow picking the same file again
  if (!file) return
  avatarBusy.value = true
  try {
    auth.setUser(await authApi.uploadAvatar(file))
    ui.toast('Photo mise à jour', 'success')
  } catch (error) {
    const message =
      error instanceof ApiError ? (error.fieldErrors.avatar?.[0] ?? error.message) : ''
    ui.toast(message || "L'envoi a échoué.", 'error')
  } finally {
    avatarBusy.value = false
  }
}

async function removeAvatar() {
  avatarBusy.value = true
  try {
    auth.setUser(await authApi.deleteAvatar())
  } finally {
    avatarBusy.value = false
  }
}

// --- E-mail (asks for the password: it is the account recovery channel) ----------
const emailData = reactive({ email: user.email, current_password: '' })
const emailForm = useFormSubmit()

async function saveEmail() {
  const ok = await emailForm.submit(async () => auth.setUser(await authApi.updateMe(emailData)))
  if (!ok) return
  emailData.current_password = ''
  ui.toast('E-mail modifié', 'success', 'Un lien de confirmation vient de partir.')
}
</script>

<template>
  <FormCard title="Photo de profil">
    <div class="flex items-center gap-4">
      <AppAvatar :name="auth.user!.display_name" :src="auth.user!.avatar_url" :size="64" />
      <div class="flex flex-wrap gap-2">
        <BaseButton variant="secondary" size="sm" :loading="avatarBusy" @click="fileInput?.click()">
          Changer
        </BaseButton>
        <BaseButton
          v-if="auth.user!.avatar_url"
          variant="ghost"
          size="sm"
          :disabled="avatarBusy"
          @click="removeAvatar"
        >
          Retirer
        </BaseButton>
      </div>
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        class="hidden"
        aria-label="Choisir une photo de profil"
        @change="onAvatarPicked"
      />
    </div>
  </FormCard>

  <FormCard title="Identité" :description="`Nom d'utilisateur : @${auth.user!.username}`">
    <form class="space-y-4" @submit.prevent="saveProfile">
      <FormError :message="profileForm.error.value" />
      <div class="grid gap-4 sm:grid-cols-2">
        <BaseInput
          v-model="profile.first_name"
          label="Prénom"
          autocomplete="given-name"
          :errors="profileForm.fieldErrors.value.first_name"
        />
        <BaseInput
          v-model="profile.last_name"
          label="Nom"
          autocomplete="family-name"
          :errors="profileForm.fieldErrors.value.last_name"
        />
      </div>
      <div class="grid gap-4 sm:grid-cols-2">
        <BaseInput
          v-model="profile.phone"
          label="Téléphone (optionnel)"
          type="tel"
          autocomplete="tel"
          :errors="profileForm.fieldErrors.value.phone"
        />
        <BaseSelect
          v-model="profile.timezone"
          label="Fuseau horaire"
          :options="timezones"
          :errors="profileForm.fieldErrors.value.timezone"
        />
      </div>
      <BaseButton type="submit" :loading="profileForm.loading.value">Enregistrer</BaseButton>
    </form>
  </FormCard>

  <FormCard
    title="Adresse e-mail"
    description="Sert aux invitations, aux notifications et à la récupération du compte."
  >
    <form class="space-y-4" @submit.prevent="saveEmail">
      <FormError :message="emailForm.error.value" />
      <BaseInput
        v-model="emailData.email"
        label="E-mail"
        type="email"
        autocomplete="email"
        required
        :errors="emailForm.fieldErrors.value.email"
      />
      <BaseInput
        v-if="emailData.email !== auth.user!.email"
        v-model="emailData.current_password"
        label="Mot de passe actuel"
        type="password"
        autocomplete="current-password"
        required
        :errors="emailForm.fieldErrors.value.current_password"
      />
      <BaseButton
        type="submit"
        :loading="emailForm.loading.value"
        :disabled="emailData.email === auth.user!.email"
      >
        Modifier l'e-mail
      </BaseButton>
    </form>
  </FormCard>
</template>

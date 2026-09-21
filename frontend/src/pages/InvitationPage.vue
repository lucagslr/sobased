<script setup lang="ts">
/**
 * Landing page of an invitation link (/invitation/:token). Public.
 * - signed in: one click to accept with the current account;
 * - signed out: create an account (the e-mail is then verified at once) or
 *   sign in and come back here.
 */
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import { type InvitationLookup, membersApi } from '@/api/projects'
import AuthCard from '@/components/ui/AuthCard.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import FormError from '@/components/ui/FormError.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useAuthStore } from '@/stores/auth'
import { useProjectsStore } from '@/stores/projects'
import { useUiStore } from '@/stores/ui'
import { useWorkspacesStore } from '@/stores/workspaces'
import { ROLE_LABELS } from '@/utils/roles'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()

const token = String(route.params.token)
const invitation = ref<InvitationLookup | null>(null)
const state = ref<'loading' | 'ready' | 'gone'>('loading')
const accepting = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    invitation.value = await membersApi.lookupInvitation(token)
    state.value = invitation.value.is_pending ? 'ready' : 'gone'
  } catch {
    state.value = 'gone'
  }
})

async function accept() {
  accepting.value = true
  error.value = ''
  try {
    const result = await membersApi.acceptInvitation(token)
    // The navigation changes: reload what the sidebar shows.
    await Promise.all([useWorkspacesStore().load(), useProjectsStore().load()])
    ui.toast('Invitation acceptée', 'success')
    router.push(result.scope_type === 'project' ? `/projets/${result.scope_id}` : '/projets')
  } catch (caught) {
    error.value =
      caught instanceof ApiError ? caught.message : "L'invitation n'a pas pu être acceptée."
  } finally {
    accepting.value = false
  }
}
</script>

<template>
  <AuthCard title="Invitation">
    <SkeletonBlock v-if="state === 'loading'" class="h-24 w-full" />

    <p v-else-if="state === 'gone'" class="rounded-lg bg-surface-2 px-4 py-3 text-sm" role="status">
      Cette invitation n'existe plus : elle a expiré, a déjà été utilisée ou a été annulée. Demande
      à la personne qui t'a invité de t'en renvoyer une.
    </p>

    <div v-else-if="invitation" class="space-y-5">
      <p class="text-[15px] leading-relaxed">
        <strong>{{ invitation.invited_by ?? "Quelqu'un" }}</strong> t'invite à rejoindre
        {{ invitation.scope_type === 'workspace' ? "l'espace" : 'le projet' }}
        <strong>{{ invitation.scope_name }}</strong> avec le rôle
        <strong>{{ ROLE_LABELS[invitation.role] }}</strong
        >.
      </p>
      <FormError :message="error" />

      <template v-if="auth.isAuthenticated">
        <BaseButton block :loading="accepting" @click="accept">
          Accepter en tant que @{{ auth.user?.username }}
        </BaseButton>
      </template>
      <template v-else>
        <RouterLink
          :to="{ name: 'register', query: { invitation: token } }"
          class="flex h-10 w-full items-center justify-center rounded-lg bg-accent text-sm font-medium text-accent-fg hover:opacity-90"
        >
          Créer mon compte
        </RouterLink>
        <RouterLink
          :to="{ name: 'login', query: { suite: route.fullPath } }"
          class="flex h-10 w-full items-center justify-center rounded-lg border border-line text-sm font-medium hover:bg-surface-2"
        >
          J'ai déjà un compte
        </RouterLink>
        <p class="text-sm text-muted">
          Invitation envoyée à {{ invitation.email }}. En créant ton compte avec cette adresse, elle
          sera confirmée automatiquement.
        </p>
      </template>
    </div>
  </AuthCard>
</template>

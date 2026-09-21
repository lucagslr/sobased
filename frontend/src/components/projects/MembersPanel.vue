<script setup lang="ts">
/**
 * Members of a workspace or of a project, Google-Drive style.
 * Shows EFFECTIVE rights: a right inherited from above is displayed with its
 * origin and cannot be edited here (only where it was granted).
 */
import { Mail, RotateCw, Trash2 } from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'

import { ApiError } from '@/api/client'
import {
  type EffectiveMember,
  type GrantableRole,
  type Invitation,
  membersApi,
  type Role,
  type Scope,
} from '@/api/projects'
import AppAvatar from '@/components/ui/AppAvatar.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { formatDate } from '@/utils/projects'
import { atLeast, ROLE_LABELS } from '@/utils/roles'

import InviteForm from './InviteForm.vue'

const props = defineProps<{
  scope: Scope
  myRole: Role | null
  canViewFinance: boolean
  canEditFinance: boolean
}>()
const emit = defineEmits<{ changed: [] }>()

const auth = useAuthStore()
const ui = useUiStore()
const members = ref<EffectiveMember[] | null>(null)
const invitations = ref<Invitation[]>([])
const toRemove = ref<EffectiveMember | null>(null)
const removing = ref(false)

const isAdmin = computed(() => atLeast(props.myRole, 'admin'))
const grantable: GrantableRole[] = ['viewer', 'commenter', 'editor', 'admin']

async function load() {
  members.value = await membersApi.list(props.scope)
  invitations.value = isAdmin.value ? await membersApi.invitations(props.scope) : []
}
onMounted(load)
watch(() => JSON.stringify(props.scope), load)

function fail(error: unknown, fallback: string) {
  ui.toast(error instanceof ApiError ? error.message : fallback, 'error')
}

async function update(member: EffectiveMember, body: Parameters<typeof membersApi.update>[1]) {
  if (!member.direct) return
  try {
    await membersApi.update(member.direct.id, body)
    await load()
    emit('changed')
  } catch (error) {
    fail(error, "La modification n'a pas pu être enregistrée.")
    await load() // put the controls back to the real values
  }
}

function setFinance(member: EffectiveMember, level: string) {
  update(member, {
    can_view_finance: level === 'view' || level === 'edit',
    can_edit_finance: level === 'edit',
  })
}

function financeLevel(member: { can_view_finance?: boolean; can_edit_finance?: boolean }) {
  if (member.can_edit_finance) return 'edit'
  return member.can_view_finance ? 'view' : 'none'
}

async function confirmRemove() {
  const member = toRemove.value
  if (!member?.direct) return
  removing.value = true
  try {
    await membersApi.remove(member.direct.id)
    toRemove.value = null
    await load()
    emit('changed')
  } catch (error) {
    fail(error, "Le retrait n'a pas fonctionné.")
  } finally {
    removing.value = false
  }
}

async function resend(invitation: Invitation) {
  try {
    await membersApi.resendInvitation(invitation.id)
    ui.toast('Invitation renvoyée', 'success', 'Le lien précédent ne fonctionne plus.')
    await load()
  } catch (error) {
    fail(error, "L'envoi a échoué.")
  }
}

async function cancel(invitation: Invitation) {
  try {
    await membersApi.cancelInvitation(invitation.id)
    await load()
  } catch (error) {
    fail(error, "L'annulation a échoué.")
  }
}

const selectClass = 'h-8 rounded-lg border border-line bg-surface px-2 text-sm disabled:opacity-60'
</script>

<template>
  <div class="space-y-6">
    <InviteForm
      v-if="isAdmin"
      :scope="scope"
      :can-grant-view="canViewFinance"
      :can-grant-edit="canEditFinance"
      @invited="load().then(() => emit('changed'))"
    />

    <div v-if="members === null" class="space-y-2">
      <SkeletonBlock v-for="n in 3" :key="n" class="h-14 w-full" />
    </div>
    <ul v-else class="divide-y divide-line rounded-xl border border-line">
      <li
        v-for="member in members"
        :key="member.user.username"
        class="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-3"
      >
        <AppAvatar :name="member.user.display_name" :src="member.user.avatar_url" :size="36" />
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-medium">
            {{ member.user.display_name }}
            <span v-if="member.user.username === auth.user?.username" class="text-muted">
              (toi)
            </span>
          </p>
          <p class="truncate text-xs text-muted">
            @{{ member.user.username }}
            <template v-for="grant in member.inherited_from" :key="grant.scope_id">
              · {{ ROLE_LABELS[grant.role] }} hérité de {{ grant.scope_name }}
            </template>
          </p>
        </div>

        <!-- Editable only if the right was granted HERE, and never for the owner. -->
        <template v-if="isAdmin && member.direct && member.direct.role !== 'owner'">
          <select
            :value="member.direct.role"
            :class="selectClass"
            :aria-label="`Rôle de ${member.user.display_name}`"
            @change="
              update(member, { role: ($event.target as HTMLSelectElement).value as GrantableRole })
            "
          >
            <option v-for="role in grantable" :key="role" :value="role">
              {{ ROLE_LABELS[role] }}
            </option>
          </select>
          <select
            :value="financeLevel(member.direct)"
            :class="selectClass"
            :aria-label="`Accès compta de ${member.user.display_name}`"
            @change="setFinance(member, ($event.target as HTMLSelectElement).value)"
          >
            <option value="none">Compta : non</option>
            <option value="view" :disabled="!canViewFinance">Compta : voir</option>
            <option value="edit" :disabled="!canEditFinance">Compta : modifier</option>
          </select>
        </template>
        <span v-else class="text-sm text-muted">
          {{ ROLE_LABELS[member.role] }}
          <template v-if="financeLevel(member) !== 'none'">
            · compta {{ financeLevel(member) === 'edit' ? 'modifiable' : 'visible' }}
          </template>
        </span>

        <button
          v-if="
            member.direct &&
            member.direct.role !== 'owner' &&
            (isAdmin || member.user.username === auth.user?.username)
          "
          type="button"
          class="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-danger"
          :aria-label="`Retirer ${member.user.display_name}`"
          @click="toRemove = member"
        >
          <Trash2 class="size-4" aria-hidden="true" />
        </button>
      </li>
    </ul>

    <div v-if="invitations.length">
      <h3 class="mb-2 text-sm font-semibold">Invitations en attente</h3>
      <ul class="divide-y divide-line rounded-xl border border-line">
        <li
          v-for="invitation in invitations"
          :key="invitation.id"
          class="flex flex-wrap items-center gap-3 px-3 py-3"
        >
          <span class="flex size-9 items-center justify-center rounded-full bg-surface-2">
            <Mail class="size-4 text-muted" aria-hidden="true" />
          </span>
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium">{{ invitation.email }}</p>
            <p class="text-xs" :class="invitation.is_pending ? 'text-muted' : 'text-danger'">
              {{ ROLE_LABELS[invitation.role] }} ·
              {{
                invitation.is_pending ? `expire le ${formatDate(invitation.expires_at)}` : 'expirée'
              }}
            </p>
          </div>
          <button
            type="button"
            class="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-fg"
            aria-label="Renvoyer l'invitation"
            @click="resend(invitation)"
          >
            <RotateCw class="size-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            class="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-danger"
            aria-label="Annuler l'invitation"
            @click="cancel(invitation)"
          >
            <Trash2 class="size-4" aria-hidden="true" />
          </button>
        </li>
      </ul>
    </div>

    <ConfirmDialog
      :open="toRemove !== null"
      :title="toRemove?.user.username === auth.user?.username ? 'Quitter ?' : 'Retirer ce membre ?'"
      confirm-label="Retirer"
      danger
      :loading="removing"
      @update:open="(value: boolean) => !value && (toRemove = null)"
      @confirm="confirmRemove"
    >
      <p>
        {{ toRemove?.user.display_name }} perdra l'accès donné ici. Un accès hérité d'un niveau
        supérieur n'est pas affecté.
      </p>
    </ConfirmDialog>
  </div>
</template>

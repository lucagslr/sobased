<script setup lang="ts">
/**
 * Invite someone by username (autocompletion) or by e-mail.
 * - username or e-mail of an existing account: access is given at once;
 * - unknown e-mail: a 14-day invitation link is e-mailed.
 */
import { useDebounceFn } from '@vueuse/core'
import { computed, reactive, ref, watch } from 'vue'

import { authApi, type PublicUser } from '@/api/auth'
import { type GrantableRole, membersApi, type Scope } from '@/api/projects'
import AppAvatar from '@/components/ui/AppAvatar.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import FormError from '@/components/ui/FormError.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useUiStore } from '@/stores/ui'
import { ROLE_HINTS, ROLE_LABELS } from '@/utils/roles'

const props = defineProps<{
  scope: Scope
  /** Finance rights the inviter holds: nobody can grant more than they have. */
  canGrantView: boolean
  canGrantEdit: boolean
}>()
const emit = defineEmits<{ invited: [] }>()

const ui = useUiStore()
const { loading, error, submit } = useFormSubmit()

const who = ref('')
const picked = ref<PublicUser | null>(null)
const suggestions = ref<PublicUser[]>([])
const form = reactive({ role: 'viewer' as GrantableRole, finance: 'default' })

const isEmail = computed(() => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(who.value.trim()))
const roleOptions = (['viewer', 'commenter', 'editor', 'admin'] as GrantableRole[]).map(
  (value) => ({ value, label: ROLE_LABELS[value] }),
)
const financeOptions = computed(() => [
  { value: 'default', label: 'Par défaut selon le rôle' },
  { value: 'none', label: 'Aucun accès à la compta' },
  ...(props.canGrantView ? [{ value: 'view', label: 'Voir la compta' }] : []),
  ...(props.canGrantEdit ? [{ value: 'edit', label: 'Voir et modifier la compta' }] : []),
])

let controller: AbortController | null = null
const search = useDebounceFn(async (query: string) => {
  controller?.abort()
  controller = new AbortController()
  try {
    suggestions.value = await authApi.searchUsers(query, controller.signal)
  } catch {
    suggestions.value = [] // aborted or throttled: just show nothing
  }
}, 250)

watch(who, (value) => {
  if (picked.value && value !== `@${picked.value.username}`) picked.value = null
  const query = value.trim()
  if (picked.value || isEmail.value || query.replace('@', '').length < 2) {
    suggestions.value = []
    return
  }
  search(query)
})

function pick(user: PublicUser) {
  picked.value = user
  who.value = `@${user.username}`
  suggestions.value = []
}

async function send() {
  const target = isEmail.value
    ? { email: who.value.trim() }
    : { username: (picked.value?.username ?? who.value).trim().replace(/^@/, '') }
  const finance =
    form.finance === 'default'
      ? {}
      : {
          can_view_finance: form.finance === 'view' || form.finance === 'edit',
          can_edit_finance: form.finance === 'edit',
        }
  let detail = ''
  const ok = await submit(async () => {
    const result = await membersApi.invite(props.scope, { ...target, role: form.role, ...finance })
    detail = result.detail
  })
  if (!ok) return
  ui.toast(detail, 'success')
  who.value = ''
  picked.value = null
  emit('invited')
}
</script>

<template>
  <form class="space-y-3" @submit.prevent="send">
    <FormError :message="error" />
    <div class="relative">
      <label for="invite-who" class="mb-1.5 block text-sm font-medium">
        Nom d'utilisateur ou e-mail
      </label>
      <input
        id="invite-who"
        v-model="who"
        type="text"
        autocomplete="off"
        placeholder="@helder ou helder@exemple.ch"
        required
        class="h-10 w-full rounded-lg border border-line bg-surface px-3 text-[15px] placeholder:text-muted"
      />
      <ul
        v-if="suggestions.length"
        class="absolute z-10 mt-1 w-full overflow-hidden rounded-xl border border-line bg-surface shadow-lg"
      >
        <li v-for="user in suggestions" :key="user.username">
          <button
            type="button"
            class="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-surface-2"
            @click="pick(user)"
          >
            <AppAvatar :name="user.display_name" :src="user.avatar_url" :size="28" />
            <span class="min-w-0">
              <span class="block truncate text-sm font-medium">{{ user.display_name }}</span>
              <span class="block truncate text-xs text-muted">@{{ user.username }}</span>
            </span>
          </button>
        </li>
      </ul>
    </div>
    <div class="grid gap-3 sm:grid-cols-2">
      <div>
        <BaseSelect v-model="form.role" label="Rôle" :options="roleOptions" />
        <p class="mt-1.5 text-xs text-muted">{{ ROLE_HINTS[form.role] }}</p>
      </div>
      <BaseSelect v-model="form.finance" label="Compta" :options="financeOptions" />
    </div>
    <BaseButton type="submit" :loading="loading">Inviter</BaseButton>
  </form>
</template>

<script setup lang="ts">
/**
 * Create or edit a share link (SPEC §10). The target is chosen once
 * (a version, an asset's latest version, or several assets); everything
 * else stays editable. After creation the panel shows the URL to copy:
 * that is the moment the user needs it.
 */
import { Check, Copy, Link2 } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

import { type Asset, filesApi } from '@/api/files'
import { type ShareLink, type ShareLinkPayload, sharingApi } from '@/api/sharing'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseSelect from '@/components/ui/BaseSelect.vue'
import BaseSwitch from '@/components/ui/BaseSwitch.vue'
import FormError from '@/components/ui/FormError.vue'
import SidePanel from '@/components/ui/SidePanel.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useUiStore } from '@/stores/ui'
import { KIND_LABELS } from '@/utils/files'
import { fromLocalInput, toLocalInput } from '@/utils/sharing'

/** What a new link points at (creation only). */
export interface ShareTargetSpec {
  /** From an asset page: its latest version, or this exact version. */
  asset?: Asset
  versionId?: number
  versionLabel?: string
  /** From a project: pick among its assets. */
  projectId?: number
}

const props = defineProps<{ link?: ShareLink | null; target?: ShareTargetSpec | null }>()
const emit = defineEmits<{ saved: [link: ShareLink] }>()
const open = defineModel<boolean>('open', { required: true })

const ui = useUiStore()
const { loading: submitting, fieldErrors, error: formError, submit } = useFormSubmit()

const title = ref('')
const recipient = ref('')
const password = ref('')
const changePassword = ref(false)
const expiresAt = ref('')
const maxViews = ref('')
const maxPlays = ref('')
const allowDownload = ref(false)
const watermark = ref(true)
const notifyOnOpen = ref(false)
const scope = ref<'asset' | 'version'>('asset')
const candidates = ref<Asset[] | null>(null)
const chosen = ref<number[]>([])
const created = ref<ShareLink | null>(null)
const copied = ref(false)

const editing = computed(() => !!props.link)
const scopeOptions = computed(() => [
  { value: 'asset', label: 'Toujours la dernière version' },
  {
    value: 'version',
    label: `Cette version seulement${props.target?.versionLabel ? ` (${props.target.versionLabel})` : ''}`,
  },
])

watch(open, async (value) => {
  if (!value) return
  created.value = null
  copied.value = false
  changePassword.value = false
  password.value = ''
  const link = props.link
  title.value = link?.title ?? props.target?.asset?.name ?? ''
  recipient.value = link?.recipient_label ?? ''
  expiresAt.value = toLocalInput(link?.expires_at ?? null)
  maxViews.value = link?.max_views != null ? String(link.max_views) : ''
  maxPlays.value = link?.max_plays != null ? String(link.max_plays) : ''
  allowDownload.value = link?.allow_download ?? false
  watermark.value = link?.watermark ?? true
  notifyOnOpen.value = link?.notify_on_open ?? false
  scope.value = 'asset'
  chosen.value = []
  candidates.value = null
  if (!link && props.target?.projectId && !props.target.asset) {
    candidates.value = await filesApi.list({
      project: props.target.projectId,
      include_descendants: true,
    })
  }
})

function toggle(id: number) {
  chosen.value = chosen.value.includes(id)
    ? chosen.value.filter((current) => current !== id)
    : [...chosen.value, id]
}

function number(value: string): number | null {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

function payload(): ShareLinkPayload {
  const base = {
    title: title.value.trim(),
    recipient_label: recipient.value.trim(),
    expires_at: fromLocalInput(expiresAt.value),
    max_views: number(maxViews.value),
    max_plays: number(maxPlays.value),
    allow_download: allowDownload.value,
    watermark: watermark.value,
    notify_on_open: notifyOnOpen.value,
  }
  const target = props.target
  if (target?.asset) {
    return scope.value === 'version' && target.versionId
      ? { ...base, target_type: 'version', version: target.versionId }
      : { ...base, target_type: 'asset', asset: target.asset.id }
  }
  if (chosen.value.length === 1) {
    return { ...base, target_type: 'asset', asset: chosen.value[0] }
  }
  return { ...base, target_type: 'playlist', project: target?.projectId, assets: chosen.value }
}

async function save() {
  await submit(async () => {
    const body = payload()
    if (props.link) {
      const patch: Record<string, unknown> = { ...body }
      delete patch.target_type
      delete patch.asset
      delete patch.version
      delete patch.assets
      delete patch.project
      if (changePassword.value) patch.password = password.value
      const updated = await sharingApi.update(props.link.id, patch)
      ui.toast('Lien mis à jour', 'success')
      emit('saved', updated)
      open.value = false
    } else {
      if (password.value) body.password = password.value
      const link = await sharingApi.create(body)
      created.value = link
      emit('saved', link)
    }
  })
}

async function copy() {
  if (!created.value?.url) return
  try {
    await navigator.clipboard.writeText(created.value.url)
    copied.value = true
    ui.toast('Lien copié', 'success')
  } catch {
    ui.toast('Copie impossible : sélectionne le lien et copie-le.', 'error')
  }
}
</script>

<template>
  <SidePanel
    v-model:open="open"
    :title="editing ? 'Modifier le lien' : created ? 'Lien créé' : 'Partager par lien'"
    :description="link?.target_label ?? target?.asset?.name"
  >
    <div v-if="created" class="space-y-4">
      <p class="text-sm text-muted">
        Ce lien ouvre une page sans compte. Envoie-le à la bonne personne ; tu pourras le révoquer à
        tout moment.
      </p>
      <div class="flex gap-2">
        <input
          :value="created.url ?? ''"
          readonly
          aria-label="Adresse du lien"
          class="h-10 min-w-0 flex-1 rounded-lg border border-line bg-surface-2 px-3 font-mono text-xs"
          @focus="($event.target as HTMLInputElement).select()"
        />
        <BaseButton variant="secondary" @click="copy">
          <Check v-if="copied" class="size-4" aria-hidden="true" />
          <Copy v-else class="size-4" aria-hidden="true" />
          Copier
        </BaseButton>
      </div>
      <ul class="space-y-1 text-sm text-muted">
        <li v-if="created.has_password">Protégé par mot de passe.</li>
        <li v-if="created.expires_at">
          Expire le {{ new Date(created.expires_at).toLocaleString('fr-CH') }}.
        </li>
        <li>{{ created.watermark ? 'Filigrane activé.' : 'Sans filigrane.' }}</li>
        <li>
          {{
            created.allow_download
              ? 'Téléchargement autorisé.'
              : 'Lecture seule, sans téléchargement.'
          }}
        </li>
      </ul>
    </div>

    <form v-else id="share-form" class="space-y-4" @submit.prevent="save">
      <template v-if="!editing && target?.asset && target.versionId">
        <BaseSelect v-model="scope" label="Ce que le lien montre" :options="scopeOptions" />
      </template>
      <fieldset v-else-if="!editing && candidates !== null" class="space-y-2">
        <legend class="text-sm font-medium">Fichiers à partager</legend>
        <p v-if="!candidates.length" class="text-sm text-muted">
          Ce projet n'a pas encore de fichier.
        </p>
        <ul v-else class="max-h-56 space-y-1 overflow-y-auto rounded-lg border border-line p-2">
          <li v-for="asset in candidates" :key="asset.id">
            <label
              class="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-surface-2"
            >
              <input
                type="checkbox"
                class="size-4 accent-fg"
                :checked="chosen.includes(asset.id)"
                @change="toggle(asset.id)"
              />
              <span class="truncate">{{ asset.name }}</span>
              <span class="ml-auto shrink-0 text-xs text-muted">{{ KIND_LABELS[asset.kind] }}</span>
            </label>
          </li>
        </ul>
        <p v-if="chosen.length > 1" class="text-xs text-muted">
          Plusieurs fichiers : la page publique les présente comme une sélection (playlist).
        </p>
        <FormError :message="fieldErrors.assets?.[0]" />
      </fieldset>

      <BaseInput
        v-model="title"
        label="Titre de la page"
        placeholder="Écoute privée · Mix titre 3"
        :errors="fieldErrors.title"
      />
      <BaseInput
        v-model="recipient"
        label="Destinataire"
        placeholder="Radio X, Programmateur Usine…"
        hint="Sert de texte de filigrane et à savoir qui a ouvert."
        :errors="fieldErrors.recipient_label"
      />

      <div
        v-if="editing && link?.has_password && !changePassword"
        class="flex items-center justify-between rounded-lg border border-line px-3 py-2 text-sm"
      >
        <span>Protégé par mot de passe</span>
        <BaseButton variant="ghost" size="sm" @click="changePassword = true">Changer</BaseButton>
      </div>
      <BaseInput
        v-else
        v-model="password"
        type="password"
        label="Mot de passe (facultatif)"
        autocomplete="new-password"
        :hint="editing ? 'Vide : aucun mot de passe.' : '4 caractères au moins.'"
        :errors="fieldErrors.password"
      />

      <BaseInput
        v-model="expiresAt"
        type="datetime-local"
        label="Expire le (facultatif)"
        :errors="fieldErrors.expires_at"
      />
      <div class="grid grid-cols-2 gap-3">
        <BaseInput
          v-model="maxViews"
          label="Vues max"
          inputmode="numeric"
          placeholder="∞"
          :errors="fieldErrors.max_views"
        />
        <BaseInput
          v-model="maxPlays"
          label="Écoutes max"
          inputmode="numeric"
          placeholder="∞"
          :errors="fieldErrors.max_plays"
        />
      </div>
      <BaseSwitch
        v-model="watermark"
        label="Filigrane"
        description="Texte sur les images, tag sonore dans l'audio."
      />
      <BaseSwitch
        v-model="allowDownload"
        label="Téléchargement autorisé"
        description="Sinon lecture seule (flux sans bouton de téléchargement)."
      />
      <BaseSwitch v-model="notifyOnOpen" label="Me prévenir à la première ouverture" />
      <FormError :message="formError" />
    </form>

    <template #footer>
      <template v-if="created">
        <BaseButton @click="open = false">Fermer</BaseButton>
      </template>
      <template v-else>
        <BaseButton variant="secondary" @click="open = false">Annuler</BaseButton>
        <BaseButton
          type="submit"
          form="share-form"
          :loading="submitting"
          :disabled="!editing && !target?.asset && chosen.length === 0"
        >
          <Link2 class="size-4" aria-hidden="true" />
          {{ editing ? 'Enregistrer' : 'Créer le lien' }}
        </BaseButton>
      </template>
    </template>
  </SidePanel>
</template>

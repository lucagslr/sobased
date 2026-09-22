<script setup lang="ts">
/**
 * The project's Google Drive folder (SPEC §11, rule D8): its link, creation
 * afterwards, the "share with members" option of a root project, and a
 * clear message when the owner account is disconnected.
 */
import { ExternalLink, FolderPlus, Users } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import { ApiError } from '@/api/client'
import { integrationsApi } from '@/api/integrations'
import { type Project, projectsApi } from '@/api/projects'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSwitch from '@/components/ui/BaseSwitch.vue'
import FormCard from '@/components/ui/FormCard.vue'
import { useUiStore } from '@/stores/ui'
import { atLeast } from '@/utils/roles'

const props = defineProps<{ project: Project }>()
const emit = defineEmits<{ changed: [] }>()

const ui = useUiStore()
const busy = ref(false)
const driveConnected = ref<boolean | null>(null)

const canEdit = computed(() => atLeast(props.project.my_role, 'editor'))
const isRoot = computed(() => props.project.parent === null)
const share = computed({
  get: () => props.project.drive_share_with_members,
  set: (value: boolean) => toggleShare(value),
})

onMounted(async () => {
  try {
    driveConnected.value = (await integrationsApi.state()).google.picker
  } catch {
    driveConnected.value = false
  }
})

async function createFolder() {
  busy.value = true
  try {
    await integrationsApi.createProjectFolder(props.project.id)
    ui.toast('Dossier Drive créé', 'success')
    emit('changed')
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : "Le dossier n'a pas été créé.", 'error')
  } finally {
    busy.value = false
  }
}

async function toggleShare(value: boolean) {
  busy.value = true
  try {
    await projectsApi.update(props.project.id, { drive_share_with_members: value })
    ui.toast(
      value
        ? 'Le dossier sera partagé avec les membres connectés à Google.'
        : 'Partage automatique désactivé.',
      'success',
    )
    emit('changed')
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'Option non enregistrée.', 'error')
  } finally {
    busy.value = false
  }
}

async function reshare() {
  busy.value = true
  try {
    const result = await integrationsApi.shareProjectFolder(props.project.id)
    ui.toast(
      `Dossier partagé avec ${result.shared_with} membre${result.shared_with > 1 ? 's' : ''}.`,
      'success',
    )
  } catch (error) {
    ui.toast(error instanceof ApiError ? error.message : 'Partage impossible.', 'error')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <FormCard
    title="Google Drive"
    description="Un dossier par projet ; les sous-projets ont le leur dans celui du parent."
  >
    <template v-if="project.drive_folder_id">
      <a
        v-if="project.drive_folder_url"
        :href="project.drive_folder_url"
        target="_blank"
        rel="noopener"
        class="inline-flex items-center gap-2 text-sm font-medium underline-offset-2 hover:underline"
      >
        <ExternalLink class="size-4" aria-hidden="true" /> Ouvrir le dossier Drive
      </a>
      <p v-if="project.drive_status === 'owner_disconnected'" class="mt-2 text-sm text-danger">
        Le compte Google propriétaire du dossier est déconnecté : le lien reste, mais la création de
        sous-dossiers et l'envoi vers Drive sont désactivés.
      </p>
      <template v-if="isRoot && canEdit">
        <BaseSwitch
          v-model="share"
          class="mt-4"
          label="Partager le dossier avec les membres connectés à Google"
          description="Lecteur → lecture, Éditeur et plus → écriture. Appliqué aux membres présents ; relance après de nouvelles arrivées."
          :disabled="busy || project.drive_status !== 'ok'"
        />
        <BaseButton
          v-if="project.drive_share_with_members && project.drive_status === 'ok'"
          variant="secondary"
          size="sm"
          class="mt-3"
          :loading="busy"
          @click="reshare"
        >
          <Users class="size-4" aria-hidden="true" /> Réappliquer le partage
        </BaseButton>
      </template>
    </template>
    <template v-else>
      <p class="text-sm text-muted">
        {{
          project.drive_status === 'parent_missing'
            ? "Le projet parent n'a pas de dossier Drive : crée-le d'abord."
            : driveConnected === false
              ? isRoot
                ? 'Connecte Google Drive (Paramètres › Intégrations) pour créer le dossier de ce projet.'
                : "Le dossier se crée dans celui du parent, avec le compte qui l'a créé."
              : 'Pas encore de dossier Drive.'
        }}
      </p>
      <BaseButton
        v-if="canEdit && project.drive_status !== 'parent_missing' && (driveConnected || !isRoot)"
        class="mt-3"
        variant="secondary"
        :loading="busy"
        @click="createFolder"
      >
        <FolderPlus class="size-4" aria-hidden="true" /> Créer le dossier
      </BaseButton>
    </template>
  </FormCard>
</template>

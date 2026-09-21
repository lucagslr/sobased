<script setup lang="ts">
/** Create a workspace (name + colour). The creator becomes its owner. */
import { reactive, watch } from 'vue'

import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import ColorPicker from '@/components/ui/ColorPicker.vue'
import FormError from '@/components/ui/FormError.vue'
import SidePanel from '@/components/ui/SidePanel.vue'
import { useFormSubmit } from '@/composables/useFormSubmit'
import { useUiStore } from '@/stores/ui'
import { useWorkspacesStore } from '@/stores/workspaces'
import { PASTEL_PALETTE } from '@/utils/projects'

const open = defineModel<boolean>('open', { required: true })
const workspaces = useWorkspacesStore()
const ui = useUiStore()
const { loading, error, fieldErrors, submit } = useFormSubmit()

const form = reactive({ name: '', color: PASTEL_PALETTE[7] })
watch(open, (isOpen) => {
  if (isOpen) Object.assign(form, { name: '', color: PASTEL_PALETTE[7] })
})

async function save() {
  const ok = await submit(async () => {
    const workspace = await workspaces.create(form.name.trim(), form.color)
    workspaces.select(workspace.id)
  })
  if (!ok) return
  ui.toast('Espace créé', 'success')
  open.value = false
}
</script>

<template>
  <SidePanel
    v-model:open="open"
    title="Nouvel espace"
    description="Un espace regroupe des projets et des membres : 100SATIONS, École, Perso…"
  >
    <form id="workspace-form" class="space-y-5" @submit.prevent="save">
      <FormError :message="error" />
      <BaseInput v-model="form.name" label="Nom" required :errors="fieldErrors.name" />
      <ColorPicker v-model="form.color" label="Couleur" />
    </form>
    <template #footer>
      <BaseButton variant="secondary" @click="open = false">Annuler</BaseButton>
      <BaseButton type="submit" form="workspace-form" :loading="loading">Créer</BaseButton>
    </template>
  </SidePanel>
</template>

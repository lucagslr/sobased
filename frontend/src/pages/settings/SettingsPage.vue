<script setup lang="ts">
/**
 * Settings shell. The section comes from the URL (/parametres/:section) so it
 * can be linked and survives a reload.
 */
import { Bell, Database, KeyRound, Layers, Palette, Plug, UserRound } from 'lucide-vue-next'
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import PageHeader from '@/components/ui/PageHeader.vue'

import AppearanceSection from './AppearanceSection.vue'
import DataSection from './DataSection.vue'
import IntegrationsSection from './IntegrationsSection.vue'
import NotificationsSection from './NotificationsSection.vue'
import ProfileSection from './ProfileSection.vue'
import SecuritySection from './SecuritySection.vue'
import WorkspacesSection from './WorkspacesSection.vue'

const SECTIONS = [
  { slug: 'profil', label: 'Profil', icon: UserRound, component: ProfileSection },
  { slug: 'espaces', label: 'Espaces', icon: Layers, component: WorkspacesSection },
  { slug: 'apparence', label: 'Apparence', icon: Palette, component: AppearanceSection },
  { slug: 'notifications', label: 'Notifications', icon: Bell, component: NotificationsSection },
  { slug: 'integrations', label: 'Intégrations', icon: Plug, component: IntegrationsSection },
  { slug: 'securite', label: 'Sécurité', icon: KeyRound, component: SecuritySection },
  { slug: 'donnees', label: 'Mes données', icon: Database, component: DataSection },
]

const route = useRoute()
const current = computed(
  () => SECTIONS.find((section) => section.slug === route.params.section) ?? SECTIONS[0],
)
</script>

<template>
  <PageHeader title="Paramètres" />

  <div class="gap-10 lg:flex">
    <!-- Horizontal, scrollable on phones; vertical list on desktop. -->
    <nav
      class="no-scrollbar -mx-4 mb-6 flex gap-1 overflow-x-auto px-4 lg:mx-0 lg:mb-0 lg:w-48 lg:shrink-0 lg:flex-col lg:px-0"
      aria-label="Sections des paramètres"
    >
      <RouterLink
        v-for="section in SECTIONS"
        :key="section.slug"
        :to="`/parametres/${section.slug}`"
        class="flex h-9 shrink-0 items-center gap-2.5 rounded-lg px-3 text-sm font-medium transition-colors"
        :class="
          section.slug === current.slug
            ? 'bg-surface-2 text-fg'
            : 'text-muted hover:bg-surface-2 hover:text-fg'
        "
        :aria-current="section.slug === current.slug ? 'page' : undefined"
      >
        <component :is="section.icon" class="size-4" aria-hidden="true" />
        {{ section.label }}
      </RouterLink>
    </nav>

    <div class="min-w-0 flex-1 space-y-5">
      <component :is="current.component" />
    </div>
  </div>
</template>

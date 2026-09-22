<script setup lang="ts">
/**
 * The bell's page (SPEC §14): my notifications, newest first, unread in
 * bold; opening one marks it read and goes where it points.
 */
import { BellOff, CheckCheck } from 'lucide-vue-next'
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import type { Notification } from '@/api/notifications'
import AppAvatar from '@/components/ui/AppAvatar.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSwitch from '@/components/ui/BaseSwitch.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SkeletonBlock from '@/components/ui/SkeletonBlock.vue'
import { useNotificationsStore } from '@/stores/notifications'
import { detail, relativeTime, sentence } from '@/utils/notifications'

const router = useRouter()
const store = useNotificationsStore()
const unreadOnly = ref(false)

onMounted(() => store.load(unreadOnly.value))
watch(unreadOnly, (value) => store.load(value))

async function open(notification: Notification) {
  await store.markRead(notification)
  if (notification.url) router.push(notification.url)
}
</script>

<template>
  <PageHeader
    title="Notifications"
    :subtitle="
      store.unread ? `${store.unread} non lue${store.unread > 1 ? 's' : ''}` : 'Tout est lu'
    "
  >
    <BaseSwitch v-model="unreadOnly" label="Non lues seulement" />
    <BaseButton v-if="store.unread" variant="secondary" size="sm" @click="store.markAllRead()">
      <CheckCheck class="size-4" aria-hidden="true" /> Tout marquer lu
    </BaseButton>
  </PageHeader>

  <div v-if="store.items === null" class="space-y-2">
    <SkeletonBlock v-for="n in 5" :key="n" class="h-14" />
  </div>
  <EmptyState
    v-else-if="!store.items.length"
    :icon="BellOff"
    title="Rien à signaler"
    text="Assignations, mentions, statuts des fichiers que tu suis, ajouts à un projet et ouvertures de liens partagés arriveront ici."
  />
  <ul v-else class="divide-y divide-line rounded-xl border border-line bg-surface">
    <li v-for="item in store.items" :key="item.id">
      <button
        type="button"
        class="flex w-full items-start gap-3 px-3 py-3 text-left hover:bg-surface-2"
        :class="item.is_read ? 'text-muted' : ''"
        @click="open(item)"
      >
        <AppAvatar
          :name="item.actor?.display_name ?? 'SOBASED'"
          :src="item.actor?.avatar_url"
          :size="32"
        />
        <span class="min-w-0 flex-1">
          <span class="block text-sm" :class="item.is_read ? '' : 'font-semibold text-fg'">
            {{ sentence(item) }}
          </span>
          <span v-if="detail(item)" class="mt-0.5 block truncate text-xs text-muted">
            {{ detail(item) }}
          </span>
        </span>
        <span class="flex shrink-0 items-center gap-2 text-xs text-muted">
          {{ relativeTime(item.created_at) }}
          <span v-if="!item.is_read" class="size-2 rounded-full bg-fg" aria-label="Non lue" />
        </span>
      </button>
    </li>
  </ul>
</template>

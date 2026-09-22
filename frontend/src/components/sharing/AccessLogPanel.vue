<script setup lang="ts">
/** Journal of a link: date, event, version, truncated IP, browser. */
import { ref, watch } from 'vue'

import { type ShareAccessLog, type ShareLink, sharingApi } from '@/api/sharing'
import SidePanel from '@/components/ui/SidePanel.vue'
import { EVENT_LABELS } from '@/utils/sharing'

const props = defineProps<{ link: ShareLink | null }>()
const open = defineModel<boolean>('open', { required: true })

const entries = ref<ShareAccessLog[] | null>(null)

watch(open, async (value) => {
  if (!value || !props.link) return
  entries.value = null
  entries.value = await sharingApi.accessLog(props.link.id)
})

function when(iso: string): string {
  return new Intl.DateTimeFormat('fr-CH', { dateStyle: 'short', timeStyle: 'short' }).format(
    new Date(iso),
  )
}

/** "Safari · iPhone", "Chrome · Windows": enough to recognise a device. */
function browser(userAgent: string): string {
  const ua = userAgent
  const name = /Edg\//.test(ua)
    ? 'Edge'
    : /OPR\//.test(ua)
      ? 'Opera'
      : /Firefox\//.test(ua)
        ? 'Firefox'
        : /Chrome\//.test(ua)
          ? 'Chrome'
          : /Safari\//.test(ua)
            ? 'Safari'
            : 'Navigateur'
  const os = /iPhone|iPad/.test(ua)
    ? 'iOS'
    : /Android/.test(ua)
      ? 'Android'
      : /Mac OS X/.test(ua)
        ? 'macOS'
        : /Windows/.test(ua)
          ? 'Windows'
          : /Linux/.test(ua)
            ? 'Linux'
            : ''
  return os ? `${name} · ${os}` : name
}
</script>

<template>
  <SidePanel v-model:open="open" title="Journal d'accès" :description="link?.title">
    <p class="mb-3 text-xs text-muted">
      Adresses IP tronquées (/24 en IPv4, /48 en IPv6) : on reconnaît un réseau, pas une personne.
    </p>
    <p v-if="entries === null" class="text-sm text-muted">Chargement…</p>
    <p v-else-if="!entries.length" class="text-sm text-muted">
      Personne n'a encore ouvert ce lien.
    </p>
    <ol v-else class="divide-y divide-line">
      <li v-for="entry in entries" :key="entry.id" class="py-2 text-sm">
        <p class="flex items-baseline justify-between gap-2">
          <span class="font-medium">
            {{ EVENT_LABELS[entry.event] }}
            <span v-if="entry.version_number" class="font-normal text-muted"
              >· v{{ entry.version_number }}</span
            >
          </span>
          <span class="shrink-0 text-xs text-muted">{{ when(entry.created_at) }}</span>
        </p>
        <p class="text-xs text-muted">
          {{ browser(entry.user_agent)
          }}<template v-if="entry.ip_truncated"> · {{ entry.ip_truncated }}</template>
        </p>
      </li>
    </ol>
  </SidePanel>
</template>

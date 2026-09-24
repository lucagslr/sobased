<script setup lang="ts">
/**
 * The public share page's frame (SPEC §10: "page publique sobre, sans
 * compte"): no navigation, no sign-in link, the theme toggle, a discreet
 * footer. The visitor is not one of ours.
 */
import { RouterView } from 'vue-router'

import ThemeToggle from '@/components/layout/ThemeToggle.vue'
</script>

<template>
  <div class="flex min-h-dvh flex-col">
    <header class="flex items-center justify-between px-5 py-4 sm:px-8">
      <span class="text-sm font-semibold tracking-[0.18em]">FAIBLEGRAINE</span>
      <ThemeToggle compact />
    </header>
    <main class="mx-auto w-full max-w-4xl flex-1 px-4 pb-16 sm:px-8">
      <RouterView />
    </main>
    <footer class="px-5 py-5 text-center text-xs text-muted">
      Partagé de façon privée avec Faiblegraine · contenu confidentiel, ne pas rediffuser.
    </footer>
  </div>
</template>

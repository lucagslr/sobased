<script setup lang="ts">
/** Centered column for public pages: sign-in, sign-up, legal, 404. */
import { RouterLink, RouterView } from 'vue-router'

import ThemeToggle from '@/components/layout/ThemeToggle.vue'
</script>

<template>
  <div class="flex min-h-dvh flex-col">
    <header class="flex items-center justify-between px-5 py-4 sm:px-8">
      <RouterLink to="/" class="text-sm font-semibold tracking-[0.18em]">SOBASED</RouterLink>
      <ThemeToggle compact />
    </header>
    <main class="flex flex-1 items-start justify-center px-4 pt-6 pb-16 sm:items-center sm:pt-0">
      <RouterView />
    </main>
    <footer class="px-5 py-5 text-center text-sm text-muted">
      <RouterLink to="/confidentialite" class="hover:text-fg">Confidentialité</RouterLink>
    </footer>
  </div>
</template>

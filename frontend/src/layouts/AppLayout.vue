<script setup lang="ts">
/**
 * Shell of the signed-in app.
 * - lg and up (>= 1024px): fixed sidebar on the left;
 * - below: content first, tab bar fixed at the bottom (thumb reach).
 */
import { RouterView } from 'vue-router'

import AppSidebar from '@/components/layout/AppSidebar.vue'
import MobileTabBar from '@/components/layout/MobileTabBar.vue'
import VerifyEmailBanner from '@/components/layout/VerifyEmailBanner.vue'
</script>

<template>
  <div class="min-h-dvh lg:pl-64">
    <AppSidebar class="fixed inset-y-0 left-0 hidden w-64 lg:flex" />
    <VerifyEmailBanner />
    <!-- pb-28 keeps the last element clear of the mobile tab bar. -->
    <main class="mx-auto w-full max-w-6xl px-4 pt-6 pb-28 sm:px-6 lg:px-10 lg:pt-10 lg:pb-12">
      <RouterView />
    </main>
    <MobileTabBar class="fixed inset-x-0 bottom-0 z-40 lg:hidden" />
  </div>
</template>

<script setup lang="ts">
import ThemeToggle from '@/components/layout/ThemeToggle.vue'
import FormCard from '@/components/ui/FormCard.vue'
</script>

<template>
  <FormCard
    title="Thème"
    description="« Système » suit le réglage clair ou sombre de ton appareil. Le choix est enregistré sur ton compte."
  >
    <ThemeToggle />
  </FormCard>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'

import AuthCard from '@/components/ui/AuthCard.vue'
</script>

<template>
  <AuthCard
    title="Page introuvable"
    subtitle="Cette adresse ne mène nulle part, ou plus nulle part."
  >
    <RouterLink to="/" class="font-medium underline">Retour à l'accueil</RouterLink>
  </AuthCard>
</template>

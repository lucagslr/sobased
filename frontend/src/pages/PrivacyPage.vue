<script setup lang="ts">
/**
 * Privacy notice (nLPD / RGPD). Plain language on purpose. Accepted at sign-up.
 * Keep it true: update this page whenever a phase changes what is collected
 * (share-link logs in phase 9, OAuth tokens in phases 10-11, export and
 * deletion in phase 13). Where the data lives and whom to write to come from
 * the server (/api/site/), so that a change of host is a change of .env.
 */
import { onMounted, ref } from 'vue'

import { siteApi, type SiteInfo } from '@/api/site'

const site = ref<SiteInfo | null>(null)

onMounted(async () => {
  try {
    site.value = await siteApi.info()
  } catch {
    /* offline: the page still reads fine without the details */
  }
})
</script>

<template>
  <article class="w-full max-w-2xl space-y-6 py-6 text-[15px] leading-relaxed">
    <header>
      <h1 class="text-2xl font-semibold tracking-tight">Confidentialité</h1>
      <p class="mt-2 text-sm text-muted">
        Comment Faiblegraine traite tes données, conformément à la nLPD (Suisse) et au RGPD.
      </p>
    </header>

    <section>
      <h2 class="mb-2 font-semibold">Qui est responsable</h2>
      <p>
        Faiblegraine est un outil de gestion de projets exploité par l'association culturelle
        100SATIONS, à Genève. Pour toute question sur tes données, écris à
        <a v-if="site?.contact_email" :href="`mailto:${site.contact_email}`" class="underline">
          {{ site.contact_email }}
        </a>
        <template v-else>l'adresse de contact de l'association</template>.
      </p>
    </section>

    <section>
      <h2 class="mb-2 font-semibold">Ce que nous enregistrons</h2>
      <ul class="list-disc space-y-1 pl-5">
        <li>
          Ton compte : nom d'utilisateur, e-mail, mot de passe (haché avec Argon2, jamais lisible),
          et si tu les renseignes : prénom, nom, téléphone, photo de profil.
        </li>
        <li>Tes préférences : thème, fuseau horaire, choix de notifications.</li>
        <li>
          Le contenu que tu crées ou qu'on partage avec toi : projets, tâches, rendez-vous,
          fichiers, commentaires, écritures comptables.
        </li>
        <li>
          Si tu connectes un compte Google ou Microsoft : les jetons d'accès, chiffrés, le temps de
          la connexion ; tu peux les révoquer à tout moment dans Paramètres.
        </li>
        <li>
          Des journaux techniques minimaux pour la sécurité (adresses IP tronquées) et un journal
          d'activité par projet, conservés 12 mois.
        </li>
      </ul>
    </section>

    <section>
      <h2 class="mb-2 font-semibold">Ce que nous ne faisons pas</h2>
      <ul class="list-disc space-y-1 pl-5">
        <li>Aucune publicité, aucun traceur tiers, aucune revente de données.</li>
        <li>Aucune ressource chargée depuis un site externe sans nécessité.</li>
        <li>
          Les autres utilisateurs ne voient de toi que ton nom d'utilisateur, ton nom affiché et ta
          photo. Jamais ton e-mail ni ton téléphone.
        </li>
      </ul>
    </section>

    <section>
      <h2 class="mb-2 font-semibold">Où sont les données</h2>
      <p v-if="site?.hosting_location === 'eu'">
        Sur un serveur situé dans l'Union européenne
        <template v-if="site.hosting_provider">(hébergeur : {{ site.hosting_provider }})</template>.
        Le RGPD s'y applique, et la Suisse reconnaît aux pays de l'Union européenne un niveau de
        protection des données adéquat.
      </p>
      <p v-else>
        Sur un serveur situé en Suisse
        <template v-if="site?.hosting_provider">(hébergeur : {{ site.hosting_provider }})</template
        >.
      </p>
      <p class="mt-2">
        Les sauvegardes sont chiffrées. Le seul cookie utilisé est celui de ta session (et son jeton
        de sécurité) : il est indispensable à la connexion et ne sert à rien d'autre.
      </p>
    </section>

    <section>
      <h2 class="mb-2 font-semibold">Tes droits</h2>
      <p>
        Tu peux consulter et corriger tes données dans Paramètres. Tu peux y demander l'export de
        tes données (fichier ZIP) et la suppression de ton compte ; ton contenu dans des projets
        partagés reste alors visible des autres membres, mais sans ton nom.
      </p>
    </section>
  </article>
</template>

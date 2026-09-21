<script setup lang="ts">
/**
 * Privacy notice (nLPD / RGPD). Plain language on purpose. Accepted at sign-up.
 * Keep it true: update this page whenever a phase changes what is collected
 * (share-link logs in phase 9, OAuth tokens in phases 10-11, export and
 * deletion in phase 13).
 */
</script>

<template>
  <article class="w-full max-w-2xl space-y-6 py-6 text-[15px] leading-relaxed">
    <header>
      <h1 class="text-2xl font-semibold tracking-tight">Confidentialité</h1>
      <p class="mt-2 text-sm text-muted">
        Comment SOBASED traite tes données, conformément à la nLPD (Suisse) et au RGPD.
      </p>
    </header>

    <section>
      <h2 class="mb-2 font-semibold">Qui est responsable</h2>
      <p>
        SOBASED est un outil de gestion de projets exploité par l'association culturelle 100SATIONS,
        à Genève. Pour toute question sur tes données, écris à l'adresse de contact de
        l'association.
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
          Des journaux techniques minimaux pour la sécurité. Les adresses IP y sont tronquées.
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
      <p>
        Sur un serveur situé en Suisse. Les sauvegardes sont chiffrées. Le seul cookie utilisé est
        celui de ta session (et son jeton de sécurité) : il est indispensable à la connexion et ne
        sert à rien d'autre.
      </p>
    </section>

    <section>
      <h2 class="mb-2 font-semibold">Tes droits</h2>
      <p>
        Tu peux consulter et corriger tes données dans Paramètres. Tu peux demander l'export de tes
        données et la suppression de ton compte ; ton contenu dans des projets partagés reste alors
        visible des autres membres, mais sans ton nom.
      </p>
    </section>
  </article>
</template>

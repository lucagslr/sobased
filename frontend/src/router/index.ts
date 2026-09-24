/**
 * Routes use French slugs (the interface is French only).
 *
 * meta.public    : reachable without a session (legal page, e-mail links...)
 * meta.guestOnly : sign-in pages; a signed-in user is sent to the dashboard
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { setUnauthorizedHandler } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    title: string
    public?: boolean
    guestOnly?: boolean
    phase?: number
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/layouts/AppLayout.vue'),
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('@/pages/DashboardPage.vue'),
        meta: { title: 'Dashboard' },
      },
      {
        path: 'notifications',
        name: 'notifications',
        component: () => import('@/pages/NotificationsPage.vue'),
        meta: { title: 'Notifications' },
      },
      {
        path: 'calendrier',
        name: 'calendar',
        component: () => import('@/pages/CalendarPage.vue'),
        meta: { title: 'Calendrier' },
      },
      {
        path: 'taches',
        name: 'my-tasks',
        component: () => import('@/pages/tasks/MyTasksPage.vue'),
        meta: { title: 'Mes tâches' },
      },
      {
        path: 'projets',
        name: 'projects',
        component: () => import('@/pages/ProjectsPage.vue'),
        meta: { title: 'Projets' },
      },
      {
        // Before the tab route: "fichiers/12" is an asset, not a tab.
        path: 'projets/:id(\\d+)/fichiers/:assetId(\\d+)',
        name: 'asset',
        component: () => import('@/pages/project/AssetPage.vue'),
        meta: { title: 'Fichier' },
      },
      {
        path: 'projets/:id(\\d+)/:tab?',
        name: 'project',
        component: () => import('@/pages/project/ProjectPage.vue'),
        meta: { title: 'Projet' },
      },
      {
        path: 'contacts',
        name: 'contacts',
        component: () => import('@/pages/ContactsPage.vue'),
        meta: { title: 'Contacts' },
      },
      {
        path: 'compta',
        name: 'finance',
        component: () => import('@/pages/FinancePage.vue'),
        meta: { title: 'Compta' },
      },
      {
        path: 'liens',
        name: 'share-links',
        component: () => import('@/pages/ShareLinksPage.vue'),
        meta: { title: 'Liens partagés' },
      },
      {
        path: 'parametres/:section?',
        name: 'settings',
        component: () => import('@/pages/settings/SettingsPage.vue'),
        meta: { title: 'Paramètres' },
      },
      {
        path: 'plus',
        name: 'more',
        component: () => import('@/pages/MorePage.vue'),
        meta: { title: 'Plus' },
      },
    ],
  },
  {
    // Public share pages: their own bare layout, no session needed.
    path: '/s',
    component: () => import('@/layouts/ShareLayout.vue'),
    children: [
      {
        path: ':token',
        name: 'share',
        component: () => import('@/pages/share/SharePage.vue'),
        meta: { title: 'Partage', public: true },
      },
    ],
  },
  {
    path: '/',
    component: () => import('@/layouts/AuthLayout.vue'),
    children: [
      {
        path: 'connexion',
        name: 'login',
        component: () => import('@/pages/auth/LoginPage.vue'),
        meta: { title: 'Connexion', public: true, guestOnly: true },
      },
      {
        path: 'inscription',
        name: 'register',
        component: () => import('@/pages/auth/RegisterPage.vue'),
        meta: { title: 'Inscription', public: true, guestOnly: true },
      },
      {
        path: 'mot-de-passe-oublie',
        name: 'forgot-password',
        component: () => import('@/pages/auth/ForgotPasswordPage.vue'),
        meta: { title: 'Mot de passe oublié', public: true, guestOnly: true },
      },
      {
        path: 'reinitialiser/:uid/:token',
        name: 'reset-password',
        component: () => import('@/pages/auth/ResetPasswordPage.vue'),
        meta: { title: 'Nouveau mot de passe', public: true },
      },
      {
        path: 'verifier-email/:token',
        name: 'verify-email',
        component: () => import('@/pages/auth/VerifyEmailPage.vue'),
        meta: { title: "Vérification de l'e-mail", public: true },
      },
      {
        path: 'invitation/:token',
        name: 'invitation',
        component: () => import('@/pages/InvitationPage.vue'),
        meta: { title: 'Invitation', public: true },
      },
      {
        path: 'confidentialite',
        name: 'privacy',
        component: () => import('@/pages/PrivacyPage.vue'),
        meta: { title: 'Confidentialité', public: true },
      },
      {
        path: ':pathMatch(.*)*',
        name: 'not-found',
        component: () => import('@/pages/NotFoundPage.vue'),
        meta: { title: 'Page introuvable', public: true },
      },
    ],
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.bootstrap()

  if (!to.meta.public && !auth.isAuthenticated) {
    // Remember where the user wanted to go.
    return { name: 'login', query: to.fullPath === '/' ? {} : { suite: to.fullPath } }
  }
  if (to.meta.guestOnly && auth.isAuthenticated) return { name: 'dashboard' }
})

router.afterEach((to, from) => {
  // Same page, new query (?tache=42 opens the task panel): keep the title the
  // page may have set itself, e.g. the name of the project.
  // (`from.matched` is empty on the very first navigation.)
  if (from.matched.length && to.path === from.path) return
  document.title = `${to.meta.title} · Faiblegraine`
})

// The session expired while the app was open: back to the login page.
setUnauthorizedHandler(() => {
  const auth = useAuthStore()
  if (!auth.isAuthenticated) return
  auth.setUser(null)
  const current = router.currentRoute.value
  if (!current.meta.public) {
    router.push({ name: 'login', query: { suite: current.fullPath } })
  }
})

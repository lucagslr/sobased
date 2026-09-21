/**
 * Routes use French slugs (the interface is French only).
 *
 * meta.public    : reachable without a session (legal page, e-mail links...)
 * meta.guestOnly : sign-in pages; a signed-in user is sent to the dashboard
 * meta.phase     : placeholder pages say in which phase the feature arrives
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

const comingSoon = () => import('@/pages/ComingSoonPage.vue')

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
        path: 'calendrier',
        name: 'calendar',
        component: comingSoon,
        meta: { title: 'Calendrier', phase: 5 },
      },
      {
        path: 'taches',
        name: 'my-tasks',
        component: comingSoon,
        meta: { title: 'Mes tâches', phase: 3 },
      },
      {
        path: 'projets',
        name: 'projects',
        component: comingSoon,
        meta: { title: 'Projets', phase: 2 },
      },
      {
        path: 'contacts',
        name: 'contacts',
        component: comingSoon,
        meta: { title: 'Contacts', phase: 6 },
      },
      {
        path: 'compta',
        name: 'finance',
        component: comingSoon,
        meta: { title: 'Compta', phase: 7 },
      },
      {
        path: 'liens',
        name: 'share-links',
        component: comingSoon,
        meta: { title: 'Liens partagés', phase: 9 },
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

router.afterEach((to) => {
  document.title = `${to.meta.title} · SOBASED`
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

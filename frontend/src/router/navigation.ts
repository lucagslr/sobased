/**
 * Single source for the main navigation: the desktop sidebar shows every
 * entry, the mobile tab bar shows the `mobile` ones plus a "Plus" tab that
 * lists the rest (SPEC §15).
 */
import {
  Bell,
  Calendar,
  CircleCheckBig,
  FolderTree,
  LayoutDashboard,
  Link2,
  Settings,
  Users,
  Wallet,
} from 'lucide-vue-next'
import type { Component } from 'vue'

export interface NavItem {
  to: string
  label: string
  /** Shorter label for the mobile tab bar. */
  shortLabel?: string
  icon: Component
  mobile: boolean
  /** Shows the unread notifications counter. */
  badge?: boolean
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, mobile: true },
  { to: '/notifications', label: 'Notifications', icon: Bell, mobile: false, badge: true },
  { to: '/calendrier', label: 'Calendrier', icon: Calendar, mobile: true },
  { to: '/taches', label: 'Mes tâches', shortLabel: 'Tâches', icon: CircleCheckBig, mobile: true },
  { to: '/projets', label: 'Projets', icon: FolderTree, mobile: true },
  { to: '/contacts', label: 'Contacts', icon: Users, mobile: false },
  { to: '/compta', label: 'Compta', icon: Wallet, mobile: false },
  { to: '/liens', label: 'Liens partagés', icon: Link2, mobile: false },
  { to: '/parametres', label: 'Paramètres', icon: Settings, mobile: false },
]

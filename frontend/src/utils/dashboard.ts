/** Widget catalogue and layout helpers of the dashboard (SPEC §15). */
import {
  CalendarClock,
  CalendarDays,
  CircleAlert,
  Pin,
  Receipt,
  Stamp,
  Sun,
  Wallet,
} from 'lucide-vue-next'
import type { Component } from 'vue'

import type { DashboardWidgets, WidgetKey, WidgetLayout } from '@/api/dashboard'

export interface WidgetMeta {
  title: string
  icon: Component
  /** Shown when the widget has nothing to list. */
  empty: string
}

export const WIDGETS: Record<WidgetKey, WidgetMeta> = {
  overdue: {
    title: 'En retard',
    icon: CircleAlert,
    empty: 'Rien en retard. Bien joué.',
  },
  today: { title: "Aujourd'hui", icon: Sun, empty: "Rien de prévu aujourd'hui." },
  pinned: {
    title: 'Todo épinglées',
    icon: Pin,
    empty: "Épingle un élément de checklist pour l'avoir sous les yeux ici.",
  },
  next7: {
    title: '7 prochains jours',
    icon: CalendarDays,
    empty: 'Aucune échéance dans les 7 prochains jours.',
  },
  to_validate: { title: 'À valider', icon: Stamp, empty: "Rien n'attend de validation." },
  meetings: { title: 'RDV à venir', icon: CalendarClock, empty: 'Aucun RDV à venir.' },
  expenses_to_pay: {
    title: 'Frais à payer ce mois',
    icon: Wallet,
    empty: 'Aucun frais à payer ce mois.',
  },
  missing_receipts: {
    title: 'Justificatifs manquants',
    icon: Receipt,
    empty: 'Tous les justificatifs sont là.',
  },
}

/** "En retard" is always first and can be neither moved nor hidden (SPEC §7). */
export const LOCKED_WIDGET: WidgetKey = 'overdue'

export const MIN_SIZE = 1
export const MAX_SIZE = 3

/**
 * Widgets to render, in order.
 * - a widget whose feature does not exist yet (`available: false`) is never shown;
 * - hidden widgets only appear while customising, so they can be brought back.
 */
export function widgetsToShow(
  layout: WidgetLayout[],
  widgets: DashboardWidgets | null,
  editing: boolean,
): WidgetLayout[] {
  return layout.filter((item) => {
    if (widgets && !widgets[item.key].available) return false
    return editing || !item.hidden
  })
}

/** Returns a new layout with one widget changed (immutably, for the store). */
export function patchWidget(
  layout: WidgetLayout[],
  key: WidgetKey,
  patch: Partial<Omit<WidgetLayout, 'key'>>,
): WidgetLayout[] {
  return layout.map((item) => {
    if (item.key !== key) return item
    const next = { ...item, ...patch }
    next.size = Math.min(MAX_SIZE, Math.max(MIN_SIZE, next.size))
    if (key === LOCKED_WIDGET) next.hidden = false
    return next
  })
}

/**
 * New order after a drag. `moved` is the list of the draggable widgets as the
 * user left them; the locked widget goes back first, and widgets that were
 * not on screen (unavailable ones) keep their slot at the end.
 */
export function reorder(layout: WidgetLayout[], moved: WidgetLayout[]): WidgetLayout[] {
  const movedKeys = new Set(moved.map((item) => item.key))
  const locked = layout.filter((item) => item.key === LOCKED_WIDGET)
  const untouched = layout.filter((item) => item.key !== LOCKED_WIDGET && !movedKeys.has(item.key))
  return [...locked, ...moved.filter((item) => item.key !== LOCKED_WIDGET), ...untouched]
}

/** Tailwind classes for a widget width (1 to 3 columns; 1 column on phones). */
export function sizeClass(size: number): string {
  if (size >= 3) return 'md:col-span-2 xl:col-span-3'
  if (size === 2) return 'md:col-span-2'
  return ''
}

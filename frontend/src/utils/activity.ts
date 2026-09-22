/**
 * French sentences of the journal (SPEC §14). Pure, tested. An entry
 * carries a verb, a target type, a label snapshot and `changes`
 * ({field: [old, new]}) whose values are display-ready (strings, numbers,
 * booleans, ISO dates, lists of names, `true`/`false` for a file).
 */
import type { ActivityEntry, ActivityVerb } from '@/api/activity'

import { STATUS_META as ASSET_STATUS } from './files'
import { FREQUENCY_LABELS, KIND_LABELS as TX_KIND, PAYMENT_STATUS_LABELS } from './finance'
import { formatAmount } from './money'
import { formatDate, STATUS_LABELS as PROJECT_STATUS } from './projects'
import { PRIORITIES, TASK_STATUS_LABELS } from './tasks'

export const VERB_LABELS: Record<ActivityVerb, string> = {
  created: 'Création',
  updated: 'Modification',
  status_changed: 'Statut',
  deleted: 'Suppression',
  shared: 'Partage',
  access_changed: 'Droits',
}
export const VERB_ORDER = Object.keys(VERB_LABELS) as ActivityVerb[]

/** "la tâche", "le RDV"… with the article the sentence needs. */
export const TARGET_LABELS: Record<string, string> = {
  task: 'la tâche',
  project: 'le projet',
  event: 'le RDV',
  asset: 'le fichier',
  asset_version: 'la version',
  share_link: 'le lien partagé',
  transaction: "l'écriture",
  budget_line: 'la ligne de budget',
  recurring_expense: 'le frais récurrent',
  membership: "l'accès de",
}

export const FIELD_LABELS: Record<string, string> = {
  title: 'titre',
  name: 'nom',
  label: 'libellé',
  status: 'statut',
  priority: 'priorité',
  start_at: 'début',
  due_at: 'échéance',
  start_date: 'début',
  end_date: 'fin',
  start: 'début',
  end: 'fin',
  all_day: 'journée entière',
  location: 'lieu',
  type: 'type',
  kind: 'type',
  assignees: 'assignés',
  parent: 'parent',
  owner: 'propriétaire',
  role: 'rôle',
  can_view_finance: 'voir la compta',
  can_edit_finance: 'modifier la compta',
  amount: 'montant',
  date: 'date',
  category: 'catégorie',
  payment_status: 'paiement',
  receipt: 'justificatif',
  frequency: 'fréquence',
  is_active: 'actif',
  version: 'version',
  expires_at: 'expiration',
  max_views: 'vues max.',
  max_plays: 'écoutes max.',
  allow_download: 'téléchargement',
}

const STATUS_BY_TARGET: Record<string, Record<string, string>> = {
  task: TASK_STATUS_LABELS,
  project: PROJECT_STATUS,
  asset: Object.fromEntries(Object.entries(ASSET_STATUS).map(([k, v]) => [k, v.label])),
  share_link: { active: 'actif', revoked: 'révoqué' },
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}/

/** One value of `changes`, in French. */
export function formatValue(field: string, value: unknown, targetType = ''): string {
  if (value === null || value === undefined || value === '') return '—'
  if (Array.isArray(value)) return value.length ? value.map(String).join(', ') : '—'
  if (typeof value === 'boolean') return value ? 'oui' : 'non'
  if (field === 'status') return STATUS_BY_TARGET[targetType]?.[String(value)] ?? String(value)
  if (field === 'priority') return PRIORITIES[Number(value)]?.label ?? String(value)
  if (field === 'amount') return `${formatAmount(String(value))} CHF`
  if (field === 'kind' && targetType === 'transaction')
    return TX_KIND[value as keyof typeof TX_KIND] ?? String(value)
  if (field === 'payment_status')
    return PAYMENT_STATUS_LABELS[value as keyof typeof PAYMENT_STATUS_LABELS] ?? String(value)
  if (field === 'frequency')
    return FREQUENCY_LABELS[value as keyof typeof FREQUENCY_LABELS] ?? String(value)
  if (typeof value === 'string' && ISO_DATE.test(value)) {
    const date = formatDate(value)
    if (value.length > 10 && !value.endsWith('T00:00:00+00:00') && !value.endsWith('T00:00:00Z')) {
      const time = new Date(value)
      if (!Number.isNaN(time.getTime())) {
        const pad = (n: number) => String(n).padStart(2, '0')
        return `${date} ${pad(time.getHours())}:${pad(time.getMinutes())}`
      }
    }
    return date
  }
  return String(value)
}

/** "titre : Brief → Brief radio", one line per changed field. */
export function describeChanges(entry: Pick<ActivityEntry, 'changes' | 'target_type'>): string[] {
  const changes = (entry.changes ?? {}) as Record<string, [unknown, unknown]>
  return Object.entries(changes).map(([field, [before, after]]) => {
    const label = FIELD_LABELS[field] ?? field
    return `${label} : ${formatValue(field, before, entry.target_type)} → ${formatValue(field, after, entry.target_type)}`
  })
}

/** "le fichier" → "du fichier", "la tâche" → "de la tâche", "l'écriture" → "de l'écriture". */
function of(label: string): string {
  if (label.startsWith('le ')) return `du ${label.slice(3)}`
  if (label.startsWith('la ')) return `de la ${label.slice(3)}`
  return `de ${label}`
}

/** "Sam a créé la tâche « Brief »", "Sam a retiré l'accès de Ana"… */
export function sentence(
  entry: Pick<ActivityEntry, 'verb' | 'target_type' | 'target_label' | 'actor' | 'changes'>,
): string {
  const actor = entry.actor?.display_name ?? 'Utilisateur supprimé'
  const target = TARGET_LABELS[entry.target_type] ?? entry.target_type
  const name = entry.target_type === 'membership' ? entry.target_label : `« ${entry.target_label} »`
  const object = `${target} ${name}`
  const ofObject = `${of(target)} ${name}`
  const changes = (entry.changes ?? {}) as Record<string, [unknown, unknown]>
  switch (entry.verb) {
    case 'created':
      return `${actor} a créé ${object}`
    case 'updated':
      if (changes.version) return `${actor} a ajouté la version ${changes.version[1]} ${ofObject}`
      if (changes.parent) return `${actor} a déplacé ${object}`
      return `${actor} a modifié ${object}`
    case 'status_changed':
      return `${actor} a passé ${object} en ${formatValue('status', changes.status?.[1], entry.target_type)}`
    case 'deleted':
      return `${actor} a supprimé ${object}`
    case 'shared':
      return `${actor} a créé ${object}`
    case 'access_changed': {
      if (changes.owner) return `${actor} a transféré la propriété ${ofObject}`
      const role = changes.role
      if (role && role[1] === null) return `${actor} a retiré ${object}`
      if (role && role[0] === null)
        return `${actor} a donné l'accès ${role[1]} à ${entry.target_label}`
      return `${actor} a modifié ${object}`
    }
    default:
      return `${actor} · ${object}`
  }
}

/** Groups entries by local day, newest first: [{day: '22.09.2026', entries}]. */
export function groupByDay(entries: ActivityEntry[]): { day: string; entries: ActivityEntry[] }[] {
  const groups: { day: string; entries: ActivityEntry[] }[] = []
  for (const entry of entries) {
    const date = new Date(entry.created_at)
    const pad = (n: number) => String(n).padStart(2, '0')
    const day = `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()}`
    const last = groups[groups.length - 1]
    if (last && last.day === day) last.entries.push(entry)
    else groups.push({ day, entries: [entry] })
  }
  return groups
}

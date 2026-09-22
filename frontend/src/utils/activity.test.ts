import { describe, expect, it } from 'vitest'

import type { ActivityEntry } from '@/api/activity'

import { describeChanges, formatValue, groupByDay, sentence } from './activity'

const sam = { username: 'sam', display_name: 'Sam', avatar_url: null }

function entry(partial: Partial<ActivityEntry>): ActivityEntry {
  return {
    id: 1,
    verb: 'created',
    actor: sam,
    project: 1,
    project_name: 'A',
    target_type: 'task',
    target_id: 3,
    target_label: 'Brief',
    changes: {},
    created_at: '2026-09-22T10:00:00Z',
    ...partial,
  }
}

describe('sentence', () => {
  it('phrases every verb', () => {
    expect(sentence(entry({}))).toBe('Sam a créé la tâche « Brief »')
    expect(sentence(entry({ verb: 'updated', changes: { title: ['a', 'b'] } }))).toBe(
      'Sam a modifié la tâche « Brief »',
    )
    expect(sentence(entry({ verb: 'status_changed', changes: { status: ['todo', 'done'] } }))).toBe(
      'Sam a passé la tâche « Brief » en Terminé',
    )
    expect(sentence(entry({ verb: 'deleted', target_type: 'event' }))).toBe(
      'Sam a supprimé le RDV « Brief »',
    )
    expect(
      sentence(entry({ verb: 'shared', target_type: 'share_link', target_label: 'Écoute' })),
    ).toBe('Sam a créé le lien partagé « Écoute »')
    expect(
      sentence(
        entry({
          verb: 'updated',
          target_type: 'asset',
          target_label: 'Cover',
          changes: { version: [1, 2] },
        }),
      ),
    ).toBe('Sam a ajouté la version 2 du fichier « Cover »')
    expect(
      sentence(entry({ verb: 'updated', target_type: 'project', changes: { parent: ['A', 'B'] } })),
    ).toBe('Sam a déplacé le projet « Brief »')
  })

  it('phrases rights', () => {
    const base = { verb: 'access_changed' as const, target_type: 'membership', target_label: 'Ana' }
    expect(sentence(entry({ ...base, changes: { role: [null, 'Lecteur'] } }))).toBe(
      "Sam a donné l'accès Lecteur à Ana",
    )
    expect(sentence(entry({ ...base, changes: { role: ['Lecteur', 'Éditeur'] } }))).toBe(
      "Sam a modifié l'accès de Ana",
    )
    expect(sentence(entry({ ...base, changes: { role: ['Éditeur', null] } }))).toBe(
      "Sam a retiré l'accès de Ana",
    )
    expect(
      sentence(
        entry({
          verb: 'access_changed',
          target_type: 'project',
          changes: { owner: ['Sam', 'Ana'] },
        }),
      ),
    ).toBe('Sam a transféré la propriété du projet « Brief »')
  })

  it('signs anonymously when the actor is gone', () => {
    expect(sentence(entry({ actor: null }))).toBe('Utilisateur supprimé a créé la tâche « Brief »')
  })
})

describe('formatValue / describeChanges', () => {
  it('speaks French for every kind of value', () => {
    expect(formatValue('status', 'in_progress', 'project')).toBe('En cours')
    expect(formatValue('status', 'approved', 'asset')).toBe('Validé')
    expect(formatValue('priority', 5)).toBe('Très haute')
    expect(formatValue('amount', '1234.5')).toBe("1'234.50 CHF")
    expect(formatValue('receipt', true)).toBe('oui')
    expect(formatValue('assignees', [])).toBe('—')
    expect(formatValue('assignees', ['Ana', 'Sam'])).toBe('Ana, Sam')
    expect(formatValue('due_at', '2026-10-12T00:00:00+00:00')).toBe('12.10.2026')
    expect(formatValue('start_date', '2026-10-12')).toBe('12.10.2026')
    expect(formatValue('title', null)).toBe('—')
  })

  it('lists the changed fields', () => {
    expect(
      describeChanges({
        target_type: 'task',
        changes: { title: ['Brief', 'Brief radio'], status: ['todo', 'done'] },
      }),
    ).toEqual(['titre : Brief → Brief radio', 'statut : À faire → Terminé'])
  })
})

describe('groupByDay', () => {
  it('keeps the order and splits on the local day', () => {
    const groups = groupByDay([
      entry({ id: 3, created_at: '2026-09-22T15:00:00Z' }),
      entry({ id: 2, created_at: '2026-09-22T09:00:00Z' }),
      entry({ id: 1, created_at: '2026-09-20T09:00:00Z' }),
    ])
    expect(groups.map((g) => [g.day, g.entries.map((e) => e.id)])).toEqual([
      ['22.09.2026', [3, 2]],
      ['20.09.2026', [1]],
    ])
  })
})

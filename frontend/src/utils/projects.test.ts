import { describe, expect, it } from 'vitest'

import type { ProjectNode } from '@/api/projects'

import { buildTree, formatDate, formatDateRange, moveTargets } from './projects'

function node(id: number, parent: number | null, name: string, position = 0): ProjectNode {
  return {
    id,
    parent,
    name,
    position,
    workspace: 1,
    depth: 1,
    color: '#BFDBFE',
    is_shell: false,
    type: null,
    type_name: null,
    status: null,
    start_date: null,
    end_date: null,
    temporal: null,
    end_overdue: false,
    tags: [],
    my_role: null,
    can_view_finance: false,
    can_edit_finance: false,
  }
}

describe('buildTree', () => {
  it('nests children under their parent, whatever the input order', () => {
    const tree = buildTree([node(3, 2, 'Clip'), node(1, null, 'SHORTY7G'), node(2, 1, 'MARCHIOLY')])

    expect(tree).toHaveLength(1)
    expect(tree[0].name).toBe('SHORTY7G')
    expect(tree[0].children[0].children[0].name).toBe('Clip')
  })

  it('sorts siblings by position, then by name', () => {
    const tree = buildTree([
      node(1, null, 'Zed', 1),
      node(2, null, 'École', 0),
      node(3, null, 'Alpha', 1),
    ])

    expect(tree.map((n) => n.name)).toEqual(['École', 'Alpha', 'Zed'])
  })

  it('keeps a node whose parent is not visible as a root', () => {
    expect(buildTree([node(5, 99, 'Orphelin')])[0].name).toBe('Orphelin')
  })
})

describe('moveTargets', () => {
  // SHORTY7G > (MARCHIOLY > (Clip > Making-of), EP2), and another root: Admin.
  const placed = (
    id: number,
    parent: number | null,
    name: string,
    depth: number,
    role: ProjectNode['my_role'] = 'editor',
  ): ProjectNode => ({ ...node(id, parent, name), depth, my_role: role })
  const nodes = [
    placed(1, null, 'SHORTY7G', 1),
    placed(2, 1, 'MARCHIOLY', 2),
    placed(3, 2, 'Clip', 3),
    placed(4, 3, 'Making-of', 4),
    placed(5, 1, 'EP2', 2),
    placed(6, null, 'Admin', 1),
  ]
  const paths = (id: number, list = nodes) => moveTargets(list, id).map((target) => target.path)

  it('excludes the project, its branch and its current parent', () => {
    // Clip (with Making-of below it) can only go where 2 levels still fit.
    expect(paths(3)).toEqual(['Admin', 'SHORTY7G', 'SHORTY7G / EP2'])
  })

  it('never proposes a place that would exceed 4 levels', () => {
    // MARCHIOLY carries 2 levels below it: only a root can host it.
    expect(paths(2)).toEqual(['Admin'])
    // A leaf fits anywhere above level 4.
    expect(paths(4)).toEqual(['Admin', 'SHORTY7G', 'SHORTY7G / EP2', 'SHORTY7G / MARCHIOLY'])
  })

  it('only proposes places where I am at least editor', () => {
    const asGuest = nodes.map((n) =>
      n.id === 6 ? { ...n, my_role: 'viewer' as const } : n.id === 1 ? { ...n, my_role: null } : n,
    )

    expect(paths(4, asGuest)).toEqual(['SHORTY7G / EP2', 'SHORTY7G / MARCHIOLY'])
  })

  it('stays inside the workspace', () => {
    const elsewhere = [...nodes, { ...placed(7, null, 'École', 1), workspace: 2 }]

    expect(paths(5, elsewhere)).not.toContain('École')
  })

  it('returns nothing for an unknown project', () => {
    expect(moveTargets(nodes, 999)).toEqual([])
  })
})

describe('dates', () => {
  it('formats the Swiss way', () => {
    expect(formatDate('2026-10-12')).toBe('12.10.2026')
    expect(formatDate(null)).toBe('')
  })

  it('describes a range with whatever is known', () => {
    expect(formatDateRange('2026-10-12', '2026-11-30')).toBe('12.10.2026 → 30.11.2026')
    expect(formatDateRange('2026-10-12', null)).toBe('dès le 12.10.2026')
    expect(formatDateRange(null, '2026-11-30')).toBe("jusqu'au 30.11.2026")
    expect(formatDateRange(null, null)).toBe('')
  })
})

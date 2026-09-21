import { describe, expect, it } from 'vitest'

import type { ProjectNode } from '@/api/projects'

import { buildTree, formatDate, formatDateRange } from './projects'

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

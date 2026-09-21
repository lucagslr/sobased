import { describe, expect, it } from 'vitest'

import type { DashboardWidgets, WidgetKey, WidgetLayout } from '@/api/dashboard'

import { patchWidget, reorder, sizeClass, widgetsToShow } from './dashboard'

const KEYS: WidgetKey[] = [
  'overdue',
  'today',
  'pinned',
  'next7',
  'to_validate',
  'meetings',
  'expenses_to_pay',
  'missing_receipts',
]

function layout(overrides: Partial<Record<WidgetKey, Partial<WidgetLayout>>> = {}): WidgetLayout[] {
  return KEYS.map((key) => ({ key, size: 1, tall: false, hidden: false, ...overrides[key] }))
}

const widgets = Object.fromEntries(
  KEYS.map((key) => [
    key,
    { available: !['meetings', 'expenses_to_pay', 'missing_receipts'].includes(key), count: 0 },
  ]),
) as unknown as DashboardWidgets

describe('widgetsToShow', () => {
  it('never shows a widget whose feature does not exist yet', () => {
    const shown = widgetsToShow(layout(), widgets, true).map((item) => item.key)

    expect(shown).toEqual(['overdue', 'today', 'pinned', 'next7', 'to_validate'])
  })

  it('hides hidden widgets, except while customising', () => {
    const current = layout({ pinned: { hidden: true } })

    expect(widgetsToShow(current, widgets, false).map((i) => i.key)).not.toContain('pinned')
    expect(widgetsToShow(current, widgets, true).map((i) => i.key)).toContain('pinned')
  })

  it('shows the layout as it is while the data is loading', () => {
    expect(widgetsToShow(layout(), null, false)).toHaveLength(KEYS.length)
  })
})

describe('patchWidget', () => {
  it('clamps the size between 1 and 3 columns', () => {
    expect(patchWidget(layout(), 'today', { size: 7 })[1].size).toBe(3)
    expect(patchWidget(layout(), 'today', { size: 0 })[1].size).toBe(1)
  })

  it('never hides "En retard"', () => {
    expect(patchWidget(layout(), 'overdue', { hidden: true })[0].hidden).toBe(false)
  })

  it('does not mutate the layout it receives', () => {
    const current = layout()
    patchWidget(current, 'today', { tall: true })

    expect(current[1].tall).toBe(false)
  })
})

describe('reorder', () => {
  it('keeps "En retard" first and parks the widgets that were not on screen', () => {
    const current = layout()
    const dragged = [current[3], current[1], current[2], current[4]] // next7 moved first

    const keys = reorder(current, dragged).map((item) => item.key)

    expect(keys).toEqual([
      'overdue',
      'next7',
      'today',
      'pinned',
      'to_validate',
      'meetings',
      'expenses_to_pay',
      'missing_receipts',
    ])
  })
})

describe('sizeClass', () => {
  it('spans more columns as the size grows, and one column on phones', () => {
    expect(sizeClass(1)).toBe('')
    expect(sizeClass(2)).toBe('md:col-span-2')
    expect(sizeClass(3)).toContain('xl:col-span-3')
  })
})

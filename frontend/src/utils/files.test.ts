import { describe, expect, it } from 'vitest'

import type { AssetComment } from '@/api/files'

import {
  anchorKind,
  buildThreads,
  commentRect,
  formatSize,
  formatTimestamp,
  rectFromDrag,
  rectPayload,
  sortThreads,
  versionLabel,
} from './files'

function comment(partial: Partial<AssetComment> & { id: number }): AssetComment {
  return {
    version: 1,
    parent: null,
    author: null,
    body: 'x',
    timestamp_ms: null,
    rect_x: null,
    rect_y: null,
    rect_w: null,
    rect_h: null,
    page: null,
    is_resolved: false,
    resolved_at: null,
    resolved_by: null,
    is_mine: false,
    edited_at: null,
    created_at: '2026-09-01T10:00:00Z',
    ...partial,
  }
}

describe('formatSize', () => {
  it('uses French units', () => {
    expect(formatSize(512)).toBe('512 o')
    expect(formatSize(12 * 1024)).toBe('12 Ko')
    expect(formatSize(3.4 * 1024 * 1024)).toBe('3,4 Mo')
    expect(formatSize(2 * 1024 * 1024 * 1024)).toBe('2 Go')
  })
})

describe('formatTimestamp', () => {
  it('formats minutes, seconds and hours', () => {
    expect(formatTimestamp(0)).toBe('0:00')
    expect(formatTimestamp(65_400)).toBe('1:05')
    expect(formatTimestamp(12 * 60_000 + 3_000)).toBe('12:03')
    expect(formatTimestamp(3_723_000)).toBe('1:02:03')
  })
})

describe('versionLabel / anchorKind', () => {
  it('labels versions', () => {
    expect(versionLabel(3, 'master')).toBe('v3 · master')
    expect(versionLabel(1, '')).toBe('v1')
  })
  it('maps kinds to anchors', () => {
    expect(anchorKind('audio')).toBe('time')
    expect(anchorKind('video')).toBe('time')
    expect(anchorKind('image')).toBe('rect')
    expect(anchorKind('document')).toBe('page')
    expect(anchorKind('other')).toBe('none')
  })
})

describe('rectangles', () => {
  it('reads a rectangle from a comment', () => {
    expect(
      commentRect(
        comment({ id: 1, rect_x: '10.500', rect_y: '20.000', rect_w: '30.000', rect_h: '15.250' }),
      ),
    ).toEqual({
      x: 10.5,
      y: 20,
      w: 30,
      h: 15.25,
    })
    expect(commentRect(comment({ id: 2 }))).toBeNull()
  })

  it('converts a drag to percentages, whatever the direction', () => {
    const rect = rectFromDrag({ x: 300, y: 150 }, { x: 100, y: 50 }, 400, 200)
    expect(rect).toEqual({ x: 25, y: 25, w: 50, h: 50 })
    expect(rectPayload(rect!)).toEqual({
      rect_x: '25.000',
      rect_y: '25.000',
      rect_w: '50.000',
      rect_h: '50.000',
    })
  })

  it('clamps to the image and ignores a plain click', () => {
    expect(rectFromDrag({ x: -50, y: 0 }, { x: 800, y: 300 }, 400, 200)).toEqual({
      x: 0,
      y: 0,
      w: 100,
      h: 100,
    })
    expect(rectFromDrag({ x: 10, y: 10 }, { x: 10, y: 10 }, 400, 200)).toBeNull()
    expect(rectFromDrag({ x: 10, y: 10 }, { x: 20, y: 20 }, 0, 0)).toBeNull()
  })
})

describe('threads', () => {
  const comments = [
    comment({ id: 1, timestamp_ms: 30_000 }),
    comment({ id: 2, parent: 1 }),
    comment({ id: 3, timestamp_ms: 5_000 }),
    comment({ id: 4 }),
    comment({ id: 5, parent: 3 }),
  ]

  it('groups replies under their root', () => {
    const threads = buildThreads(comments)
    expect(threads.map((t) => [t.root.id, t.replies.map((r) => r.id)])).toEqual([
      [1, [2]],
      [3, [5]],
      [4, []],
    ])
  })

  it('sorts by anchor, unanchored last', () => {
    const sorted = sortThreads(buildThreads(comments), 'time')
    expect(sorted.map((t) => t.root.id)).toEqual([3, 1, 4])
    const byId = sortThreads(buildThreads(comments), 'none')
    expect(byId.map((t) => t.root.id)).toEqual([1, 3, 4])
  })

  it('sorts rectangles top to bottom then left to right', () => {
    const rects = [
      comment({ id: 1, rect_x: '50', rect_y: '10', rect_w: '5', rect_h: '5' }),
      comment({ id: 2, rect_x: '5', rect_y: '10', rect_w: '5', rect_h: '5' }),
      comment({ id: 3, rect_x: '0', rect_y: '0', rect_w: '5', rect_h: '5' }),
    ]
    expect(sortThreads(buildThreads(rects), 'rect').map((t) => t.root.id)).toEqual([3, 2, 1])
  })
})

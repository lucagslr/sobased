/**
 * Share links (SPEC §10): the editors' API and the public page's endpoints.
 * Public calls carry no session of ours: the visitor's anonymous session
 * (cookie) is what binds the media URLs to their browser.
 */
import { api } from './client'
import type { components } from './schema'
import type { Paginated } from './tasks'

type Schemas = components['schemas']

export type ShareLink = Schemas['ShareLink']
export type ShareLinkPayload = Schemas['ShareLinkRequest']
export type ShareLinkPatch = Schemas['PatchedShareLinkRequest']
export type ShareAccessLog = Schemas['AccessLog']
export type ShareState = Schemas['ShareStateEnum']
export type ShareTarget = Schemas['ShareTargetEnum']
export type ShareEvent = Schemas['ShareEventEnum']
export type PublicShare = Schemas['PublicShare']
export type PublicItem = Schemas['PublicItem']

export interface ShareFilters {
  project?: number
  include_descendants?: boolean
  workspace?: number
  state?: ShareState | ''
}

function query(filters: ShareFilters): string {
  const params = new URLSearchParams({ page_size: '200' })
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  return `?${params.toString()}`
}

export const sharingApi = {
  list: (filters: ShareFilters = {}) =>
    api<Paginated<ShareLink>>(`/api/share-links/${query(filters)}`).then((page) => page.results),
  get: (id: number) => api<ShareLink>(`/api/share-links/${id}/`),
  create: (body: ShareLinkPayload) => api<ShareLink>('/api/share-links/', { method: 'POST', body }),
  update: (id: number, body: ShareLinkPatch) =>
    api<ShareLink>(`/api/share-links/${id}/`, { method: 'PATCH', body }),
  revoke: (id: number) => api<ShareLink>(`/api/share-links/${id}/revoke/`, { method: 'POST' }),
  remove: (id: number) => api(`/api/share-links/${id}/`, { method: 'DELETE' }),
  accessLog: (id: number) => api<ShareAccessLog[]>(`/api/share-links/${id}/access-log/`),

  /** Public page. 404: unknown, 410: gone (the ApiError carries the status). */
  open: (token: string) => api<PublicShare>(`/api/public/share/${encodeURIComponent(token)}/`),
  unlock: (token: string, password: string) =>
    api<PublicShare>(`/api/public/share/${encodeURIComponent(token)}/unlock/`, {
      method: 'POST',
      body: { password },
    }),
}

/**
 * Files: assets, their numbered versions, anchored comments, statuses.
 *
 * Uploads go through XMLHttpRequest, the only way to report progress on a
 * 500 MB file; everything else uses the api() wrapper. Binary content
 * (original, stream, peaks, thumbnail) is fetched by URL: the endpoints
 * check the rights and Caddy streams the file.
 */
import { ApiError, api, csrfToken, parseErrorBody } from './client'
import type { components } from './schema'
import type { Paginated } from './tasks'

type Schemas = components['schemas']

export type Asset = Schemas['Asset']
export type AssetVersion = Schemas['AssetVersion']
export type AssetComment = Schemas['AssetComment']
export type AssetStatusChange = Schemas['StatusChange']
export type AssetKind = Schemas['AssetKindEnum']
export type AssetStatus = Schemas['AssetStatusEnum']

export interface AssetFilters {
  project?: number
  include_descendants?: boolean
  workspace?: number
  kind?: AssetKind | ''
  status?: AssetStatus | ''
  tag?: number
  search?: string
  ordering?: string
}

export interface CommentPayload {
  body: string
  parent?: number | null
  timestamp_ms?: number | null
  rect_x?: string | null
  rect_y?: string | null
  rect_w?: string | null
  rect_h?: string | null
  page?: number | null
}

export interface UploadFields {
  /** Asset creation only. */
  project?: number
  name?: string
  label?: string
  note?: string
}

function query(filters: AssetFilters): string {
  const params = new URLSearchParams({ page_size: '200' })
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  return `?${params.toString()}`
}

/**
 * Multipart POST with upload progress (0..1). Resolves with the JSON body,
 * rejects with an ApiError shaped like api()'s so forms treat both alike.
 */
export function upload<T>(
  path: string,
  file: File,
  fields: UploadFields,
  onProgress?: (ratio: number) => void,
  signal?: AbortSignal,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const form = new FormData()
    for (const [key, value] of Object.entries(fields)) {
      if (value !== undefined && value !== null) form.append(key, String(value))
    }
    form.append('file', file)
    const xhr = new XMLHttpRequest()
    xhr.open('POST', path)
    xhr.setRequestHeader('Accept', 'application/json')
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(event.loaded / event.total)
    }
    xhr.onerror = () =>
      reject(new ApiError(0, 'Connexion au serveur impossible. Vérifie ton réseau.'))
    xhr.onabort = () => reject(new DOMException('Envoi annulé', 'AbortError'))
    xhr.onload = () => {
      let data: unknown = null
      try {
        data = xhr.responseText ? JSON.parse(xhr.responseText) : null
      } catch {
        data = null
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data as T)
        return
      }
      if (xhr.status === 413) {
        reject(new ApiError(413, 'Fichier trop lourd pour le serveur.', { file: ['Trop lourd.'] }))
        return
      }
      const { message, fieldErrors } = parseErrorBody(data)
      reject(new ApiError(xhr.status, message, fieldErrors))
    }
    signal?.addEventListener('abort', () => xhr.abort())
    csrfToken().then((token) => {
      xhr.setRequestHeader('X-CSRFToken', token)
      xhr.send(form)
    }, reject)
  })
}

export const filesApi = {
  list: (filters: AssetFilters = {}) =>
    api<Paginated<Asset>>(`/api/assets/${query(filters)}`).then((page) => page.results),
  get: (id: number) => api<Asset>(`/api/assets/${id}/`),
  create: (
    file: File,
    fields: Required<Pick<UploadFields, 'project' | 'name'>> & UploadFields,
    onProgress?: (ratio: number) => void,
    signal?: AbortSignal,
  ) => upload<Asset>('/api/assets/', file, fields, onProgress, signal),
  update: (id: number, body: { name?: string; kind?: AssetKind; tags?: number[] }) =>
    api<Asset>(`/api/assets/${id}/`, { method: 'PATCH', body }),
  remove: (id: number) => api(`/api/assets/${id}/`, { method: 'DELETE' }),
  changeStatus: (id: number, status: AssetStatus, note = '') =>
    api<Asset>(`/api/assets/${id}/status/`, { method: 'POST', body: { status, note } }),
  statusHistory: (id: number) => api<AssetStatusChange[]>(`/api/assets/${id}/status-history/`),
  follow: (id: number) => api<Asset>(`/api/assets/${id}/follow/`, { method: 'POST' }),
  unfollow: (id: number) => api<Asset>(`/api/assets/${id}/follow/`, { method: 'DELETE' }),

  versions: (assetId: number) => api<AssetVersion[]>(`/api/assets/${assetId}/versions/`),
  addVersion: (
    assetId: number,
    file: File,
    fields: Pick<UploadFields, 'label' | 'note'>,
    onProgress?: (ratio: number) => void,
    signal?: AbortSignal,
  ) => upload<AssetVersion>(`/api/assets/${assetId}/versions/`, file, fields, onProgress, signal),
  version: (id: number) => api<AssetVersion>(`/api/asset-versions/${id}/`),
  updateVersion: (id: number, body: { label?: string; note?: string }) =>
    api<AssetVersion>(`/api/asset-versions/${id}/`, { method: 'PATCH', body }),
  removeVersion: (id: number) => api(`/api/asset-versions/${id}/`, { method: 'DELETE' }),
  downloadUrl: (version: AssetVersion) => `${version.file_url}?download=1`,

  comments: (versionId: number) =>
    api<AssetComment[]>(`/api/asset-versions/${versionId}/comments/`),
  addComment: (versionId: number, body: CommentPayload) =>
    api<AssetComment>(`/api/asset-versions/${versionId}/comments/`, { method: 'POST', body }),
  editComment: (id: number, body: string) =>
    api<AssetComment>(`/api/asset-comments/${id}/`, { method: 'PATCH', body: { body } }),
  removeComment: (id: number) => api(`/api/asset-comments/${id}/`, { method: 'DELETE' }),
  resolve: (id: number) =>
    api<AssetComment>(`/api/asset-comments/${id}/resolve/`, { method: 'POST' }),
  reopen: (id: number) =>
    api<AssetComment>(`/api/asset-comments/${id}/reopen/`, { method: 'POST' }),
}

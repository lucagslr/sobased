/** Contacts (the address book of a workspace) and their links to projects. */
import { api } from './client'
import type { components } from './schema'

type Schemas = components['schemas']

export type Contact = Schemas['Contact']
export type ContactLink = Schemas['ContactLink']
export type ProjectContact = Schemas['ProjectContact']

export interface ContactPayload {
  workspace?: number
  /** Create AND link to this project at once (how a project guest adds one). */
  project?: number
  role_label?: string
  first_name?: string
  last_name?: string
  organization?: string
  job?: string
  email?: string
  phone?: string
  instagram?: string
  website?: string
  notes?: string
  tags?: number[]
}

export interface ContactFilters {
  workspace?: number
  /** Contacts linked to this project or its sub-projects. */
  project?: number
  tag?: number
  job?: string
  search?: string
}

function query(filters: ContactFilters): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

export const contactsApi = {
  list: (filters: ContactFilters = {}) => api<Contact[]>(`/api/contacts/${query(filters)}`),
  get: (id: number) => api<Contact>(`/api/contacts/${id}/`),
  create: (body: ContactPayload) => api<Contact>('/api/contacts/', { method: 'POST', body }),
  update: (id: number, body: ContactPayload) =>
    api<Contact>(`/api/contacts/${id}/`, { method: 'PATCH', body }),
  remove: (id: number) => api(`/api/contacts/${id}/`, { method: 'DELETE' }),

  links: (project: number, includeDescendants = false) =>
    api<ProjectContact[]>(
      `/api/project-contacts/?project=${project}${includeDescendants ? '&include_descendants=true' : ''}`,
    ),
  link: (project: number, contact: number, role_label = '') =>
    api<ProjectContact>('/api/project-contacts/', {
      method: 'POST',
      body: { project, contact, role_label },
    }),
  relabel: (linkId: number, role_label: string) =>
    api<ProjectContact>(`/api/project-contacts/${linkId}/`, {
      method: 'PATCH',
      body: { role_label },
    }),
  unlink: (linkId: number) => api(`/api/project-contacts/${linkId}/`, { method: 'DELETE' }),
}

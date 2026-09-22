/** Events and meetings (RDV). */
import { api } from './client'
import type { components } from './schema'
import type { Paginated, RecurrenceScope } from './tasks'

type Schemas = components['schemas']

export type Event = Schemas['Event']
export type EventType = Schemas['EventTypeEnum']
export type EventContact = Schemas['EventContact']

export interface EventPayload {
  project?: number
  type?: EventType
  title?: string
  start?: string
  end?: string
  all_day?: boolean
  location?: string
  prep_notes?: string
  report?: string
  decisions?: string[]
  participant_usernames?: string[]
  contacts?: number[]
  tags?: number[]
  /** RRULE. "" stops the recurrence (with scope "following"). */
  rrule?: string
}

export interface EventFilters {
  project?: number
  include_descendants?: boolean
  workspace?: number
  participant?: string
  type?: EventType
  /** Calendars: events that cross [window_start, window_end[. */
  window_start?: string
  window_end?: string
  page?: number
  page_size?: number
  ordering?: string
}

const MAX_PAGES = 20

function query(filters: EventFilters): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null) params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

export const eventsApi = {
  list: (filters: EventFilters = {}) =>
    api<Paginated<Event>>(`/api/events/${query({ page_size: 200, ...filters })}`),
  /** Every page of `list`, in order (calendars, agendas). */
  async listAll(filters: EventFilters = {}, signal?: AbortSignal): Promise<Event[]> {
    const events: Event[] = []
    for (let page = 1; page <= MAX_PAGES; page += 1) {
      const chunk = await api<Paginated<Event>>(
        `/api/events/${query({ page_size: 200, ...filters, page })}`,
        { signal },
      )
      events.push(...chunk.results)
      if (!chunk.next) break
    }
    return events
  },
  get: (id: number) => api<Event>(`/api/events/${id}/`),
  create: (body: EventPayload & { project: number; title: string; start: string }) =>
    api<Event>('/api/events/', { method: 'POST', body }),
  update: (id: number, body: EventPayload, scope: RecurrenceScope = 'this') =>
    api<Event>(`/api/events/${id}/?scope=${scope}`, { method: 'PATCH', body }),
  remove: (id: number, scope: RecurrenceScope = 'this') =>
    api(`/api/events/${id}/?scope=${scope}`, { method: 'DELETE' }),
}

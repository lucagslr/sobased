/** The activity journal of a project (SPEC §14): editors and up. */
import { api } from './client'
import type { components } from './schema'
import type { Paginated } from './tasks'

type Schemas = components['schemas']

export type ActivityEntry = Schemas['ActivityEntry']
export type ActivityVerb = Schemas['VerbEnum']

export interface ActivityQuery {
  project: number
  include_descendants?: boolean
  verb?: ActivityVerb | ''
  target_type?: string
  actor?: string
  page?: number
}

export const activityApi = {
  list: (query: ActivityQuery) => {
    const params = new URLSearchParams({ project: String(query.project), page_size: '50' })
    if (query.include_descendants) params.set('include_descendants', 'true')
    if (query.verb) params.set('verb', query.verb)
    if (query.target_type) params.set('target_type', query.target_type)
    if (query.actor) params.set('actor', query.actor)
    if (query.page && query.page > 1) params.set('page', String(query.page))
    return api<Paginated<ActivityEntry>>(`/api/activity/?${params}`)
  },
}

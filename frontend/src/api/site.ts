/** Public constants of the instance (privacy page): where the data is hosted, whom to write to. */
import { api } from './client'
import type { components } from './schema'

export type SiteInfo = components['schemas']['SiteInfo']

export const siteApi = {
  info: () => api<SiteInfo>('/api/site/'),
}

/** The bell (SPEC §14): my notifications and their unread counter. */
import { api } from './client'
import type { components } from './schema'
import type { Paginated } from './tasks'

type Schemas = components['schemas']

export type Notification = Schemas['Notification']
export type NotificationKind = Schemas['NotificationKindEnum']

export const notificationsApi = {
  list: (unreadOnly = false) =>
    api<Paginated<Notification>>(
      `/api/notifications/?page_size=100${unreadOnly ? '&unread=true' : ''}`,
    ).then((page) => page.results),
  unreadCount: () => api<{ unread: number }>('/api/notifications/unread-count/'),
  markRead: (id: number) => api<Notification>(`/api/notifications/${id}/read/`, { method: 'POST' }),
  markAllRead: () => api('/api/notifications/read-all/', { method: 'POST' }),
}

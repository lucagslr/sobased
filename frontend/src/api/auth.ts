/** Calls for /api/auth/*, /api/me/ and /api/users/*. Types come from OpenAPI. */
import { api } from './client'
import type { components } from './schema'

export type Me = components['schemas']['Me']
export type PublicUser = components['schemas']['PublicUser']
export type Theme = NonNullable<Me['theme']>

export interface RegisterPayload {
  username: string
  email: string
  password: string
  first_name?: string
  last_name?: string
  accept_privacy: boolean
}

export const authApi = {
  /** Session probe: answers 200 with `user: null` when signed out. */
  session: () => api<{ user: Me | null }>('/api/auth/session/'),
  me: () => api<Me>('/api/me/'),
  login: (username: string, password: string) =>
    api<Me>('/api/auth/login/', { method: 'POST', body: { username, password }, silent401: true }),
  logout: () => api('/api/auth/logout/', { method: 'POST' }),
  register: (payload: RegisterPayload) =>
    api<Me>('/api/auth/register/', { method: 'POST', body: payload }),
  verifyEmail: (token: string) =>
    api('/api/auth/verify-email/', { method: 'POST', body: { token } }),
  resendVerification: () => api('/api/auth/verify-email/resend/', { method: 'POST' }),
  requestPasswordReset: (email: string) =>
    api('/api/auth/password/reset/', { method: 'POST', body: { email } }),
  confirmPasswordReset: (uid: string, token: string, new_password: string) =>
    api('/api/auth/password/reset/confirm/', {
      method: 'POST',
      body: { uid, token, new_password },
    }),
  changePassword: (current_password: string, new_password: string) =>
    api('/api/auth/password/change/', {
      method: 'POST',
      body: { current_password, new_password },
    }),
  updateMe: (patch: Partial<Me> & { current_password?: string }) =>
    api<Me>('/api/me/', { method: 'PATCH', body: patch }),
  uploadAvatar: (file: File) => {
    const formData = new FormData()
    formData.append('avatar', file)
    return api<Me>('/api/me/avatar/', { method: 'PUT', formData })
  },
  deleteAvatar: () => api<Me>('/api/me/avatar/', { method: 'DELETE' }),
  searchUsers: (query: string, signal?: AbortSignal) =>
    api<PublicUser[]>(`/api/users/search/?q=${encodeURIComponent(query)}`, { signal }),
}

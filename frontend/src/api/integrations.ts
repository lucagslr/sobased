/** External accounts (Google, Microsoft), Google Picker, Drive links and folders. */
import { api } from './client'
import type { Project } from './projects'
import type { components } from './schema'

type Schemas = components['schemas']

export type IntegrationsState = Schemas['IntegrationsState']
export type ProviderState = Schemas['ProviderState']
export type PickerConfig = Schemas['PickerConfig']
export type DriveLink = Schemas['DriveLink']
export type DriveStatus = Schemas['DriveStatusEnum']

export const integrationsApi = {
  state: () => api<IntegrationsState>('/api/integrations/'),
  /** The Google consent page for these features; the browser goes there. */
  googleConnectUrl: (features: ('drive' | 'calendar')[] = ['drive']) =>
    api<Schemas['ConnectUrl']>(
      `/api/integrations/google/connect/?features=${features.join(',')}`,
    ).then((data) => data.url),
  googleDisconnect: () => api('/api/integrations/google/', { method: 'DELETE' }),
  pickerConfig: () => api<PickerConfig>('/api/integrations/google/picker-config/'),

  driveLinks: (filters: { project?: number; task?: number }) => {
    const params = new URLSearchParams()
    if (filters.project) params.set('project', String(filters.project))
    if (filters.task) params.set('task', String(filters.task))
    return api<DriveLink[]>(`/api/drive-links/?${params.toString()}`)
  },
  attachDriveFile: (project: number, drive_file_id: string, task?: number | null) =>
    api<DriveLink>('/api/drive-links/', {
      method: 'POST',
      body: { project, drive_file_id, task: task ?? null },
    }),
  removeDriveLink: (id: number) => api(`/api/drive-links/${id}/`, { method: 'DELETE' }),

  createProjectFolder: (project: number) =>
    api<Project>(`/api/projects/${project}/drive/create-folder/`, { method: 'POST' }),
  shareProjectFolder: (project: number) =>
    api<Project & { shared_with: number }>(`/api/projects/${project}/drive/share/`, {
      method: 'POST',
    }),
  uploadToDrive: (project: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api<DriveLink>(`/api/projects/${project}/drive/upload/`, {
      method: 'POST',
      formData: form,
    })
  },
}

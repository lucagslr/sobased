/** Workspaces, projects, memberships, invitations, project types and tags. */
import { api } from './client'
import type { components } from './schema'

type Schemas = components['schemas']

export type Workspace = Schemas['Workspace']
export type ProjectNode = Schemas['ProjectNode']
export type Project = Schemas['Project']
export type ProjectType = Schemas['ProjectType']
export type Tag = Schemas['Tag']
export type Role = Schemas['RoleEnum']
export type GrantableRole = Schemas['GrantableRoleEnum']
export type ProjectStatus = Schemas['ProjectStatusEnum']
export type Temporal = Schemas['TemporalEnum']
export type TasksView = Schemas['TasksViewEnum']
export type ProjectCard = Schemas['ProjectCard']
export type CardEntry = Schemas['CardEntry']
export type EffectiveMember = Schemas['EffectiveMember']
export type Invitation = Schemas['Invitation']
export type InvitationLookup = Schemas['InvitationLookup']
export type InviteResult = Schemas['InviteResult']

/** A project the user only sees as a shell (ancestor of what they can access). */
export interface ShellProject {
  id: number
  workspace: number
  parent: number | null
  depth: number
  name: string
  color: string
  is_shell: true
  breadcrumb: Project['breadcrumb']
}

/** A scope is either a workspace or a project (memberships and invitations). */
export type Scope = { workspace: number } | { project: number }

function scopeQuery(scope: Scope): string {
  return 'workspace' in scope ? `workspace=${scope.workspace}` : `project=${scope.project}`
}

export interface ProjectPayload {
  workspace?: number
  parent?: number | null
  name: string
  description?: string
  type?: number
  status?: ProjectStatus
  start_date?: string | null
  end_date?: string | null
  color?: string
  tags?: number[]
}

export interface InvitePayload {
  username?: string
  email?: string
  role: GrantableRole
  can_view_finance?: boolean
  can_edit_finance?: boolean
}

export const workspacesApi = {
  list: () => api<Workspace[]>('/api/workspaces/'),
  create: (body: { name: string; color: string }) =>
    api<Workspace>('/api/workspaces/', { method: 'POST', body }),
  update: (id: number, body: Partial<{ name: string; color: string }>) =>
    api<Workspace>(`/api/workspaces/${id}/`, { method: 'PATCH', body }),
  remove: (id: number) => api(`/api/workspaces/${id}/`, { method: 'DELETE' }),
  leave: (id: number) => api(`/api/workspaces/${id}/leave/`, { method: 'POST' }),
  transferOwnership: (id: number, username: string) =>
    api<Workspace>(`/api/workspaces/${id}/transfer-ownership/`, {
      method: 'POST',
      body: { username },
    }),

  projectTypes: (workspace: number) =>
    api<ProjectType[]>(`/api/project-types/?workspace=${workspace}`),
  createProjectType: (workspace: number, name: string) =>
    api<ProjectType>('/api/project-types/', { method: 'POST', body: { workspace, name } }),
  renameProjectType: (id: number, name: string) =>
    api<ProjectType>(`/api/project-types/${id}/`, { method: 'PATCH', body: { name } }),
  removeProjectType: (id: number) => api(`/api/project-types/${id}/`, { method: 'DELETE' }),

  tags: (workspace: number) => api<Tag[]>(`/api/tags/?workspace=${workspace}`),
  createTag: (workspace: number, name: string, color: string) =>
    api<Tag>('/api/tags/', { method: 'POST', body: { workspace, name, color } }),
  updateTag: (id: number, body: Partial<{ name: string; color: string }>) =>
    api<Tag>(`/api/tags/${id}/`, { method: 'PATCH', body }),
  removeTag: (id: number) => api(`/api/tags/${id}/`, { method: 'DELETE' }),
}

export const projectsApi = {
  tree: (includeArchived = false) =>
    api<ProjectNode[]>(`/api/projects/tree/${includeArchived ? '?include_archived=true' : ''}`),
  get: (id: number) => api<Project | ShellProject>(`/api/projects/${id}/`),
  create: (body: ProjectPayload) => api<Project>('/api/projects/', { method: 'POST', body }),
  update: (id: number, body: Partial<ProjectPayload>) =>
    api<Project>(`/api/projects/${id}/`, { method: 'PATCH', body }),
  remove: (id: number) => api(`/api/projects/${id}/`, { method: 'DELETE' }),
  move: (id: number, parent: number | null) =>
    api<Project>(`/api/projects/${id}/move/`, { method: 'POST', body: { parent } }),
  /** "Cartes" mode: one card per root project (all workspaces if omitted). */
  cards: (workspace?: number) =>
    api<ProjectCard[]>(`/api/projects/cards/${workspace ? `?workspace=${workspace}` : ''}`),
  /** Remembers the task view I use on this project (follows me across devices). */
  setMyState: (id: number, tasksView: TasksView) =>
    api<{ tasks_view: TasksView }>(`/api/projects/${id}/my-state/`, {
      method: 'PATCH',
      body: { tasks_view: tasksView },
    }),
  transferOwnership: (id: number, username: string) =>
    api<Project>(`/api/projects/${id}/transfer-ownership/`, {
      method: 'POST',
      body: { username },
    }),
}

export const membersApi = {
  list: (scope: Scope) => api<EffectiveMember[]>(`/api/memberships/?${scopeQuery(scope)}`),
  invite: (scope: Scope, payload: InvitePayload) =>
    api<InviteResult>('/api/memberships/', { method: 'POST', body: { ...scope, ...payload } }),
  update: (
    id: number,
    body: Partial<{ role: GrantableRole; can_view_finance: boolean; can_edit_finance: boolean }>,
  ) => api(`/api/memberships/${id}/`, { method: 'PATCH', body }),
  remove: (id: number) => api(`/api/memberships/${id}/`, { method: 'DELETE' }),

  invitations: (scope: Scope) => api<Invitation[]>(`/api/invitations/?${scopeQuery(scope)}`),
  cancelInvitation: (id: number) => api(`/api/invitations/${id}/`, { method: 'DELETE' }),
  resendInvitation: (id: number) => api(`/api/invitations/${id}/resend/`, { method: 'POST' }),
  lookupInvitation: (token: string) =>
    api<InvitationLookup>(`/api/invitations/lookup/${encodeURIComponent(token)}/`),
  acceptInvitation: (token: string) =>
    api<{ scope_type: 'workspace' | 'project'; scope_id: number }>('/api/invitations/accept/', {
      method: 'POST',
      body: { token },
    }),
}

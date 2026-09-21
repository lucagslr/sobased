/** Dashboard: widget data, saved views, project overview, end-date queue. */
import { api } from './client'
import type { components } from './schema'

type Schemas = components['schemas']

export type DashboardView = Schemas['DashboardView']
export type ViewFilters = Schemas['ViewFilters']
export type WidgetLayout = Schemas['WidgetLayout']
export type WidgetKey = Schemas['WidgetKeyEnum']
export type DashboardSummary = Schemas['DashboardSummary']
export type DashboardWidgets = Schemas['DashboardWidgets']
export type ValidateItem = Schemas['ValidateItem']
export type ProjectOverview = Schemas['ProjectOverview']
export type Milestone = Schemas['Milestone']
export type OverdueProject = Schemas['OverdueProject']

export const dashboardApi = {
  summary: (viewId: number) => api<DashboardSummary>(`/api/dashboard/summary/?view=${viewId}`),

  /** The first call creates "Mon dashboard" server-side: never empty. */
  views: () => api<DashboardView[]>('/api/dashboard/views/'),
  createView: (body: { name: string; filters?: ViewFilters; is_default?: boolean }) =>
    api<DashboardView>('/api/dashboard/views/', { method: 'POST', body }),
  updateView: (
    id: number,
    body: Partial<Pick<DashboardView, 'name' | 'filters' | 'layout' | 'is_default'>>,
  ) => api<DashboardView>(`/api/dashboard/views/${id}/`, { method: 'PATCH', body }),
  removeView: (id: number) => api(`/api/dashboard/views/${id}/`, { method: 'DELETE' }),

  projectOverview: (projectId: number) =>
    api<ProjectOverview>(`/api/projects/${projectId}/overview/`),

  overdueProjects: () => api<OverdueProject[]>('/api/projects/overdue/'),
  snoozeOverdue: (projectId: number) =>
    api(`/api/projects/${projectId}/snooze-overdue/`, { method: 'POST' }),
}

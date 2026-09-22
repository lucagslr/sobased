/** Tasks, checklist items and comments. */
import { api } from './client'
import type { components } from './schema'

type Schemas = components['schemas']

export type Task = Schemas['Task']
export type TaskStatus = Schemas['TaskStatusEnum']
export type ChecklistItem = Schemas['ChecklistItem']
/** GET /api/checklist-items/?pinned=true adds the context the dashboard needs
 * (the OpenAPI schema only describes the plain item for this endpoint). */
export type PinnedItem = ChecklistItem & {
  task_title: string
  project: number
  project_name: string
  project_color: string
}
export type TaskComment = Schemas['TaskComment']
export type Blocker = Schemas['Blocker']
export type BlockerCandidate = Schemas['BlockerCandidate']
export type SourceEvent = Schemas['SourceEvent']

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface TaskPayload {
  project?: number
  title?: string
  description?: string
  status?: TaskStatus
  priority?: number
  start_at?: string | null
  due_at?: string | null
  all_day?: boolean
  assignee_usernames?: string[]
  tags?: number[]
  blocked_by?: number[]
  /** RRULE. "" stops the recurrence (with scope "following"). */
  rrule?: string
  /** The meeting the task comes from (creation only). */
  source_event?: number | null
}

/** "this" occurrence only, or this one and all the "following" (recurring tasks). */
export type RecurrenceScope = 'this' | 'following'

export interface TaskFilters {
  project?: number
  include_descendants?: boolean
  workspace?: number
  assignee?: string
  open?: boolean
  overdue?: boolean
  /** Calendar and Gantt: tasks whose span crosses [window_start, window_end[. */
  window_start?: string
  window_end?: string
  page?: number
  page_size?: number
  ordering?: string
}

/** Boards and timelines need every task, not the first page. 20 pages of 200
 * is far above what a project holds; the cap only stops a runaway loop. */
const MAX_PAGES = 20

function query(filters: TaskFilters): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null) params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

export type MovedTask = Task & { warning?: string }

export const tasksApi = {
  list: (filters: TaskFilters = {}) =>
    api<Paginated<Task>>(`/api/tasks/${query({ page_size: 200, ...filters })}`),
  /** Every page of `list`, in order (kanban, calendar, Gantt). */
  async listAll(filters: TaskFilters = {}, signal?: AbortSignal): Promise<Task[]> {
    const tasks: Task[] = []
    for (let page = 1; page <= MAX_PAGES; page += 1) {
      const chunk = await api<Paginated<Task>>(
        `/api/tasks/${query({ page_size: 200, ...filters, page })}`,
        { signal },
      )
      tasks.push(...chunk.results)
      if (!chunk.next) break
    }
    return tasks
  },
  get: (id: number) => api<Task>(`/api/tasks/${id}/`),
  create: (body: TaskPayload & { project: number; title: string }) =>
    api<Task>('/api/tasks/', { method: 'POST', body }),
  update: (id: number, body: TaskPayload, scope: RecurrenceScope = 'this') =>
    api<Task>(`/api/tasks/${id}/?scope=${scope}`, { method: 'PATCH', body }),
  remove: (id: number, scope: RecurrenceScope = 'this') =>
    api(`/api/tasks/${id}/?scope=${scope}`, { method: 'DELETE' }),
  move: (id: number, status: TaskStatus, position: number) =>
    api<MovedTask>(`/api/tasks/${id}/move/`, { method: 'POST', body: { status, position } }),
  blockerCandidates: (taskId: number, search: string, signal?: AbortSignal) =>
    api<BlockerCandidate[]>(
      `/api/tasks/blocker-candidates/?task=${taskId}&q=${encodeURIComponent(search)}`,
      { signal },
    ),

  addChecklistItem: (taskId: number, title: string) =>
    api<ChecklistItem>(`/api/checklist-items/?task=${taskId}`, {
      method: 'POST',
      body: { title },
    }),
  updateChecklistItem: (
    id: number,
    body: Partial<Pick<ChecklistItem, 'title' | 'done' | 'pinned' | 'position'>>,
  ) => api<ChecklistItem>(`/api/checklist-items/${id}/`, { method: 'PATCH', body }),
  removeChecklistItem: (id: number) => api(`/api/checklist-items/${id}/`, { method: 'DELETE' }),
  pinnedItems: (project?: number) =>
    api<PinnedItem[]>(`/api/checklist-items/?pinned=true${project ? `&project=${project}` : ''}`),

  comments: (taskId: number) => api<TaskComment[]>(`/api/task-comments/?task=${taskId}`),
  addComment: (taskId: number, body: string) =>
    api<TaskComment>(`/api/task-comments/?task=${taskId}`, { method: 'POST', body: { body } }),
  updateComment: (id: number, body: string) =>
    api<TaskComment>(`/api/task-comments/${id}/`, { method: 'PATCH', body: { body } }),
  removeComment: (id: number) => api(`/api/task-comments/${id}/`, { method: 'DELETE' }),
}

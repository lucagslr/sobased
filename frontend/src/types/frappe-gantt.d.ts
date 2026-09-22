/** frappe-gantt ships no types: only what TaskGanttView.vue uses is declared. */
declare module 'frappe-gantt' {
  export interface GanttTask {
    id: string
    name: string
    start: string
    end: string
    progress: number
    dependencies: string
    color?: string
    custom_class?: string
  }

  export type GanttViewMode = 'Day' | 'Week' | 'Month'

  export interface GanttOptions {
    view_mode?: GanttViewMode
    language?: string
    /** `false` disables the built-in popup (it renders names as HTML). */
    popup?: false
    readonly?: boolean
    readonly_progress?: boolean
    move_dependencies?: boolean
    today_button?: boolean
    view_mode_select?: boolean
    infinite_padding?: boolean
    scroll_to?: 'today' | 'start' | 'end' | string
    bar_height?: number
    padding?: number
    container_height?: number | 'auto'
    on_click?: (task: GanttTask) => void
    on_date_change?: (task: GanttTask, start: Date, end: Date) => void
  }

  export default class Gantt {
    constructor(wrapper: HTMLElement | string, tasks: GanttTask[], options?: GanttOptions)
    /** Replaces the rows without drawing (follow with update_options). */
    setup_tasks(tasks: GanttTask[]): void
    refresh(tasks: GanttTask[]): void
    change_view_mode(mode: GanttViewMode, maintainPosition?: boolean): void
    update_options(options: GanttOptions): void
  }
}

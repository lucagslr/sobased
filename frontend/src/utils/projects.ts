/** Labels, palette and tree helpers for projects. */
import type { ProjectNode, ProjectStatus, Temporal } from '@/api/projects'

export const STATUS_LABELS: Record<ProjectStatus, string> = {
  idea: 'Idée',
  planned: 'Planifié',
  in_progress: 'En cours',
  to_validate: 'À valider',
  done: 'Terminé',
  cancelled: 'Annulé',
  archived: 'Archivé',
}
export const STATUS_ORDER = Object.keys(STATUS_LABELS) as ProjectStatus[]

export const TEMPORAL_LABELS: Record<Temporal, string> = {
  past: 'Passé',
  current: 'En cours',
  upcoming: 'À venir',
}

/**
 * The pastel palette (SPEC §15): the only colours of the interface, reserved
 * for projects, tags and priorities. Soft enough for both themes.
 */
export const PASTEL_PALETTE = [
  '#FECACA', // rose
  '#FED7AA', // orange
  '#FDE68A', // yellow
  '#D9F99D', // lime
  '#BBF7D0', // green
  '#99F6E4', // teal
  '#BAE6FD', // sky
  '#BFDBFE', // blue
  '#C7D2FE', // indigo
  '#DDD6FE', // violet
  '#F5D0FE', // fuchsia
  '#FBCFE8', // pink
  '#E7E5E4', // stone
  '#CBD5E1', // slate
]

export const MAX_DEPTH = 4

export interface TreeNode extends ProjectNode {
  children: TreeNode[]
}

/** Nests the flat list returned by GET /api/projects/tree/. */
export function buildTree(nodes: ProjectNode[]): TreeNode[] {
  const byId = new Map<number, TreeNode>()
  for (const node of nodes) byId.set(node.id, { ...node, children: [] })
  const roots: TreeNode[] = []
  for (const node of byId.values()) {
    const parent = node.parent === null ? undefined : byId.get(node.parent)
    if (parent) parent.children.push(node)
    else roots.push(node) // a root, or a node whose parent is not visible
  }
  const sort = (list: TreeNode[]) => {
    list.sort((a, b) => a.position - b.position || a.name.localeCompare(b.name, 'fr'))
    list.forEach((node) => sort(node.children))
  }
  sort(roots)
  return roots
}

export interface MoveTarget {
  id: number
  /** "SHORTY7G / MARCHIOLY": where the project would land. */
  path: string
}

/**
 * Projects `projectId` may be moved under (SPECIFICATIONS §2): same workspace,
 * not itself nor its own branch, not its current parent, a place where I am
 * at least editor, and never deeper than 4 levels once its branch follows.
 * The server checks all of it again; this only keeps impossible choices out
 * of the list.
 */
export function moveTargets(nodes: ProjectNode[], projectId: number): MoveTarget[] {
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const project = byId.get(projectId)
  if (!project) return []

  const branch = new Set([projectId])
  let grew = true
  while (grew) {
    grew = false
    for (const node of nodes) {
      if (node.parent !== null && branch.has(node.parent) && !branch.has(node.id)) {
        branch.add(node.id)
        grew = true
      }
    }
  }
  const deepest = Math.max(...[...branch].map((id) => byId.get(id)!.depth))
  const height = deepest - project.depth // levels below the project

  const path = (node: ProjectNode): string => {
    const parent = node.parent === null ? undefined : byId.get(node.parent)
    return parent ? `${path(parent)} / ${node.name}` : node.name
  }
  const canHost = (node: ProjectNode) =>
    node.my_role === 'editor' || node.my_role === 'admin' || node.my_role === 'owner'

  return nodes
    .filter(
      (node) =>
        node.workspace === project.workspace &&
        !branch.has(node.id) &&
        node.id !== project.parent &&
        canHost(node) &&
        node.depth + 1 + height <= MAX_DEPTH,
    )
    .map((node) => ({ id: node.id, path: path(node) }))
    .sort((a, b) => a.path.localeCompare(b.path, 'fr'))
}

/** 12.10.2026 (Swiss format). Empty string when there is no date. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const [year, month, day] = iso.slice(0, 10).split('-')
  return `${day}.${month}.${year}`
}

/** "12.10.2026 → 30.11.2026", "dès le …", "jusqu'au …" or "". */
export function formatDateRange(start?: string | null, end?: string | null): string {
  if (start && end) return `${formatDate(start)} → ${formatDate(end)}`
  if (start) return `dès le ${formatDate(start)}`
  if (end) return `jusqu'au ${formatDate(end)}`
  return ''
}

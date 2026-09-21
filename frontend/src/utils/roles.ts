/** Role labels and comparison. Mirrors apps/projects/access.py (Role ranks). */
import type { Role } from '@/api/projects'

export const ROLE_ORDER: Role[] = ['viewer', 'commenter', 'editor', 'admin', 'owner']

export const ROLE_LABELS: Record<Role, string> = {
  viewer: 'Lecteur',
  commenter: 'Commentateur',
  editor: 'Éditeur',
  admin: 'Admin',
  owner: 'Propriétaire',
}

export const ROLE_HINTS: Record<Role, string> = {
  viewer: 'Voit tout, ne modifie rien.',
  commenter: 'Voit, commente et annote.',
  editor: 'Crée, modifie et supprime le contenu.',
  admin: 'Éditeur + gère les membres et les droits.',
  owner: 'Tous les droits, y compris la suppression.',
}

/** `null` (no role, e.g. a shell) is never enough. */
export function atLeast(role: Role | null | undefined, minimum: Role): boolean {
  if (!role) return false
  return ROLE_ORDER.indexOf(role) >= ROLE_ORDER.indexOf(minimum)
}

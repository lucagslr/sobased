/**
 * Thin fetch wrapper for the Django API.
 *
 * - Same origin, session cookie: nothing to store on the client.
 * - Every write sends the CSRF token read from the `csrftoken` cookie.
 * - Errors become ApiError, with DRF field errors already split out so that
 *   forms can display them under the right input.
 */

export type FieldErrors = Record<string, string[]>

export class ApiError extends Error {
  status: number
  fieldErrors: FieldErrors

  constructor(status: number, message: string, fieldErrors: FieldErrors = {}) {
    super(message)
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

/** Called when the API answers 401 on a page that needs a session. */
let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

async function ensureCsrfCookie() {
  if (!getCookie('csrftoken')) {
    await fetch('/api/auth/csrf/', { credentials: 'same-origin' })
  }
}

const GENERIC_ERROR = 'Une erreur est survenue. Réessaie dans un instant.'

/** Turns a DRF error body into a message + per-field errors. */
export function parseErrorBody(body: unknown): { message: string; fieldErrors: FieldErrors } {
  if (!body || typeof body !== 'object') return { message: GENERIC_ERROR, fieldErrors: {} }
  const data = body as Record<string, unknown>
  const fieldErrors: FieldErrors = {}
  for (const [key, value] of Object.entries(data)) {
    if (key === 'detail') continue
    fieldErrors[key] = Array.isArray(value) ? value.map(String) : [String(value)]
  }
  const nonField = fieldErrors.non_field_errors?.[0]
  const message =
    typeof data.detail === 'string'
      ? data.detail
      : (nonField ??
        (Object.keys(fieldErrors).length ? 'Certains champs sont invalides.' : GENERIC_ERROR))
  return { message, fieldErrors }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** JSON body. Use `formData` instead for file uploads. */
  body?: unknown
  formData?: FormData
  signal?: AbortSignal
  /** Set on calls where a 401 is an expected answer (session probe, login). */
  silent401?: boolean
}

export async function api<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = { Accept: 'application/json' }

  if (method !== 'GET') {
    await ensureCsrfCookie()
    headers['X-CSRFToken'] = getCookie('csrftoken') ?? ''
  }
  let body: BodyInit | undefined
  if (options.formData) {
    body = options.formData // the browser sets the multipart boundary itself
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  let response: Response
  try {
    response = await fetch(path, {
      method,
      headers,
      body,
      credentials: 'same-origin',
      signal: options.signal,
    })
  } catch (error) {
    if ((error as Error).name === 'AbortError') throw error
    throw new ApiError(0, 'Connexion au serveur impossible. Vérifie ton réseau.')
  }

  if (response.status === 204) return undefined as T
  const isJson = response.headers.get('content-type')?.includes('application/json')
  const data = isJson ? await response.json() : null

  if (!response.ok) {
    if (response.status === 401 && !options.silent401) onUnauthorized?.()
    if (response.status === 429) {
      throw new ApiError(429, data?.detail ?? 'Trop de tentatives. Réessaie plus tard.')
    }
    const { message, fieldErrors } = parseErrorBody(data)
    throw new ApiError(response.status, message, fieldErrors)
  }
  return data as T
}

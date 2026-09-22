/**
 * Google Picker on demand (SPEC §11): the Google script is only loaded when
 * the user asks to pick a file, never at start-up. The Picker runs with the
 * user's own short-lived access token (drive.file: it grants the app access
 * to exactly the files picked). Returns the picked file ids.
 *
 * Types are declared minimally here: the Picker is a small surface and
 * @types/google.picker would be one more dependency for four calls.
 */
import { ref } from 'vue'

import { ApiError } from '@/api/client'
import { integrationsApi } from '@/api/integrations'

export interface PickedFile {
  id: string
  name: string
  mimeType: string
}

interface PickerDoc {
  id: string
  name: string
  mimeType: string
}

interface GoogleApi {
  load: (name: string, callback: () => void) => void
}

interface PickerBuilder {
  addView: (view: unknown) => PickerBuilder
  setOAuthToken: (token: string) => PickerBuilder
  setDeveloperKey: (key: string) => PickerBuilder
  setAppId: (id: string) => PickerBuilder
  setLocale: (locale: string) => PickerBuilder
  enableFeature: (feature: unknown) => PickerBuilder
  setCallback: (callback: (data: { action: string; docs?: PickerDoc[] }) => void) => PickerBuilder
  build: () => { setVisible: (visible: boolean) => void }
}

interface PickerNamespace {
  PickerBuilder: new () => PickerBuilder
  DocsView: new (viewId?: unknown) => { setIncludeFolders: (b: boolean) => unknown }
  ViewId: { DOCS: unknown }
  Feature: { MULTISELECT_ENABLED: unknown }
  Action: { PICKED: string; CANCEL: string }
}

declare global {
  interface Window {
    gapi?: GoogleApi
    google?: { picker?: PickerNamespace }
  }
}

const SCRIPT_URL = 'https://apis.google.com/js/api.js'
let scriptPromise: Promise<void> | null = null

function loadScript(): Promise<void> {
  if (window.google?.picker) return Promise.resolve()
  if (!scriptPromise) {
    scriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = SCRIPT_URL
      script.async = true
      script.onload = () => {
        window.gapi?.load('picker', () => resolve())
      }
      script.onerror = () => {
        scriptPromise = null
        reject(new Error('Le script Google Picker ne se charge pas.'))
      }
      document.head.appendChild(script)
    })
  }
  return scriptPromise
}

export function useGooglePicker() {
  const opening = ref(false)
  const error = ref('')

  /** Resolves with the picked files (empty when cancelled). */
  async function pick(multiple = false): Promise<PickedFile[]> {
    opening.value = true
    error.value = ''
    try {
      const config = await integrationsApi.pickerConfig()
      await loadScript()
      const picker = window.google?.picker
      if (!picker) throw new Error('Google Picker indisponible.')
      return await new Promise<PickedFile[]>((resolve) => {
        const view = new picker.DocsView(picker.ViewId.DOCS)
        view.setIncludeFolders(false)
        let builder = new picker.PickerBuilder()
          .addView(view)
          .setOAuthToken(config.access_token)
          .setDeveloperKey(config.api_key)
          .setAppId(config.app_id)
          .setLocale('fr')
          .setCallback((data) => {
            if (data.action === picker.Action.PICKED) {
              resolve(
                (data.docs ?? []).map((doc) => ({
                  id: doc.id,
                  name: doc.name,
                  mimeType: doc.mimeType,
                })),
              )
            } else if (data.action === picker.Action.CANCEL) {
              resolve([])
            }
          })
        if (multiple) builder = builder.enableFeature(picker.Feature.MULTISELECT_ENABLED)
        builder.build().setVisible(true)
      })
    } catch (caught) {
      error.value =
        caught instanceof ApiError ? caught.message : ((caught as Error).message ?? 'Erreur.')
      return []
    } finally {
      opening.value = false
    }
  }

  return { pick, opening, error }
}

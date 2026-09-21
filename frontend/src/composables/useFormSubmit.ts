/**
 * Shared plumbing for forms that call the API: a `loading` flag, the general
 * error message, and the per-field errors returned by DRF.
 */
import { ref } from 'vue'

import { ApiError, type FieldErrors } from '@/api/client'

export function useFormSubmit() {
  const loading = ref(false)
  const error = ref('')
  const fieldErrors = ref<FieldErrors>({})

  /** Runs `action`; returns true on success, false after recording the error. */
  async function submit(action: () => Promise<unknown>): Promise<boolean> {
    loading.value = true
    error.value = ''
    fieldErrors.value = {}
    try {
      await action()
      return true
    } catch (caught) {
      if (caught instanceof ApiError) {
        fieldErrors.value = caught.fieldErrors
        // With field errors under the inputs, a generic banner is just noise.
        error.value = Object.keys(caught.fieldErrors).length ? '' : caught.message
      } else {
        error.value = 'Une erreur est survenue.'
      }
      return false
    } finally {
      loading.value = false
    }
  }

  return { loading, error, fieldErrors, submit }
}

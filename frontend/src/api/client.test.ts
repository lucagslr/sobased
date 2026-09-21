import { describe, expect, it } from 'vitest'

import { parseErrorBody } from './client'

describe('parseErrorBody', () => {
  it('reads a DRF "detail" message', () => {
    expect(parseErrorBody({ detail: 'Lien invalide ou expiré.' })).toEqual({
      message: 'Lien invalide ou expiré.',
      fieldErrors: {},
    })
  })

  it('splits field errors', () => {
    const parsed = parseErrorBody({ username: ['Déjà pris.'], password: ['Trop court.'] })
    expect(parsed.fieldErrors.username).toEqual(['Déjà pris.'])
    expect(parsed.message).toBe('Certains champs sont invalides.')
  })

  it('promotes non_field_errors to the main message', () => {
    expect(parseErrorBody({ non_field_errors: ['Impossible.'] }).message).toBe('Impossible.')
  })

  it('survives an empty or non-JSON body', () => {
    expect(parseErrorBody(null).message).toMatch(/erreur/i)
  })
})

/** Theme handling. Keep the storage key and rule in sync with public/theme-init.js. */
export type ThemeChoice = 'light' | 'dark' | 'system'

export const THEME_STORAGE_KEY = 'sobased-theme'

export function isThemeChoice(value: unknown): value is ThemeChoice {
  return value === 'light' || value === 'dark' || value === 'system'
}

/** 'system' follows the OS preference; the two others are explicit. */
export function resolveTheme(choice: ThemeChoice, prefersDark: boolean): 'light' | 'dark' {
  if (choice === 'system') return prefersDark ? 'dark' : 'light'
  return choice
}

export function applyTheme(choice: ThemeChoice) {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const dark = resolveTheme(choice, prefersDark) === 'dark'
  document.documentElement.classList.toggle('dark', dark)
}

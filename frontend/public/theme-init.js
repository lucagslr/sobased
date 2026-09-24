// Runs before the app bundle to avoid a flash of the wrong theme.
// Must stay in sync with src/utils/theme.ts (same storage key, same rule).
;(function () {
  try {
    var theme = localStorage.getItem('faiblegraine-theme') || 'system'
    var dark =
      theme === 'dark' ||
      (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
    document.documentElement.classList.toggle('dark', dark)
  } catch (e) {
    /* localStorage unavailable: keep the light default */
  }
})()

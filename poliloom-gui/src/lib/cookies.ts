const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365

// === Generic cookie utilities (client-side) ===

export function setCookie(name: string, value: string, maxAgeSeconds = ONE_YEAR_SECONDS): void {
  if (typeof document === 'undefined') return
  document.cookie = `${name}=${value}; Max-Age=${maxAgeSeconds}; Path=/; SameSite=Lax`
}

export function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const prefix = `${name}=`
  const match = document.cookie
    .split(';')
    .map((c) => c.trim())
    .find((c) => c.startsWith(prefix))
  return match ? match.slice(prefix.length) : null
}

export function hasCookie(name: string): boolean {
  return getCookie(name) !== null
}

// === Filter cookies ===

export const FILTER_LANGUAGES_COOKIE = 'poliloom_filter_languages'
export const FILTER_COUNTRIES_COOKIE = 'poliloom_filter_countries'

export function serializeFilterCookieValue(qids: string[]): string {
  return encodeURIComponent(qids.join(','))
}

export function deserializeFilterCookieValue(raw: string | undefined): string[] {
  if (!raw) return []
  try {
    const decoded = decodeURIComponent(raw)
    if (!decoded) return []
    return decoded.split(',').filter((v) => /^Q\d+$/.test(v))
  } catch {
    return []
  }
}

export function writeFilterCookie(name: string, qids: string[]): void {
  setCookie(name, serializeFilterCookieValue(qids))
}

export function readFilterCookie(name: string): string[] {
  return deserializeFilterCookieValue(getCookie(name) ?? undefined)
}

// === Theme cookies ===

export const THEME_COOKIE = 'poliloom_theme'
export type Theme = 'light' | 'dark'

export function serializeThemeCookieValue(theme: Theme): string {
  return theme
}

export function deserializeThemeCookieValue(raw: string | undefined): Theme | null {
  return raw === 'light' || raw === 'dark' ? raw : null
}

export function writeThemeCookie(theme: Theme): void {
  setCookie(THEME_COOKIE, theme)
}

export function readThemeCookie(): Theme | null {
  return deserializeThemeCookieValue(getCookie(THEME_COOKIE) ?? undefined)
}

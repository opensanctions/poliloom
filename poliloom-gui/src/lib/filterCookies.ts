import { getCookie, setCookie } from './cookies'

export const FILTER_LANGUAGES_COOKIE = 'poliloom_filter_languages'
export const FILTER_COUNTRIES_COOKIE = 'poliloom_filter_countries'

export function parseFilterCookieValue(raw: string | undefined): string[] {
  if (!raw) return []
  try {
    const json = decodeURIComponent(raw)
    const parsed: unknown = JSON.parse(json)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((v): v is string => typeof v === 'string')
  } catch {
    return []
  }
}

export function writeFilterCookie(name: string, qids: string[]): void {
  setCookie(name, encodeURIComponent(JSON.stringify(qids)))
}

export function readFilterCookie(name: string): string[] {
  return parseFilterCookieValue(getCookie(name) ?? undefined)
}

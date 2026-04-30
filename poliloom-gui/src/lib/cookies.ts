const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365

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

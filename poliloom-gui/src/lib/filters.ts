import { cookies } from 'next/headers'
import { getCountries, getLanguages } from '@/lib/api-auth'
import {
  FILTER_COUNTRIES_COOKIE,
  FILTER_LANGUAGES_COOKIE,
  deserializeFilterCookieValue,
} from '@/lib/cookies'

// Returns null when no cookie is set, so callers can choose between autodetect
// and a default. Stale QIDs (no longer in the API list) are filtered out.
export async function getFilterLanguageQids(): Promise<string[] | null> {
  const cookieStore = await cookies()
  const raw = cookieStore.get(FILTER_LANGUAGES_COOKIE)?.value
  if (raw === undefined) return null
  const valid = new Set((await getLanguages()).map((l) => l.wikidata_id))
  return deserializeFilterCookieValue(raw).filter((q) => valid.has(q))
}

export async function getFilterCountryQids(): Promise<string[]> {
  const cookieStore = await cookies()
  const raw = cookieStore.get(FILTER_COUNTRIES_COOKIE)?.value
  if (raw === undefined) return []
  const valid = new Set((await getCountries()).map((c) => c.wikidata_id))
  return deserializeFilterCookieValue(raw).filter((q) => valid.has(q))
}

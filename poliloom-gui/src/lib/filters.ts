import { cookies, headers } from 'next/headers'
import { getCountries, getLanguages } from '@/lib/api-auth'
import { detectAcceptLanguage } from '@/lib/detectAcceptLanguage'
import {
  FILTER_COUNTRIES_COOKIE,
  FILTER_LANGUAGES_COOKIE,
  deserializeFilterCookieValue,
} from '@/lib/cookies'

export async function resolveLanguageQids(): Promise<string[]> {
  const cookieStore = await cookies()
  const raw = cookieStore.get(FILTER_LANGUAGES_COOKIE)?.value
  const languages = await getLanguages()
  const valid = new Set(languages.map((language) => language.wikidata_id))
  const cookieQids = raw ? deserializeFilterCookieValue(raw).filter((qid) => valid.has(qid)) : []
  if (cookieQids.length > 0) return cookieQids

  const detectedQids = detectAcceptLanguage((await headers()).get('accept-language'), languages)
  return detectedQids.length > 0 ? detectedQids : ['Q1860']
}

export async function getFilterCountryQids(): Promise<string[]> {
  const cookieStore = await cookies()
  const raw = cookieStore.get(FILTER_COUNTRIES_COOKIE)?.value
  if (raw === undefined) return []
  const valid = new Set((await getCountries()).map((c) => c.wikidata_id))
  return deserializeFilterCookieValue(raw).filter((q) => valid.has(q))
}

import { LanguageResponse, WikidataEntity } from '@/types'

export function detectBrowserLanguage(availableLanguages: LanguageResponse[]): WikidataEntity[] {
  try {
    const browserLanguages = navigator.languages || [navigator.language]
    const iso639Codes = browserLanguages.map((lang) => lang.split('-')[0].toLowerCase())

    const matched: WikidataEntity[] = []
    for (const code of iso639Codes) {
      const found = availableLanguages.find(
        (lang) => lang.iso_639_1?.toLowerCase() === code || lang.iso_639_3?.toLowerCase() === code,
      )
      if (found && !matched.some((m) => m.wikidata_id === found.wikidata_id)) {
        matched.push({ wikidata_id: found.wikidata_id, name: found.name })
      }
    }
    return matched
  } catch (error) {
    console.warn('Failed to detect browser language:', error)
    return []
  }
}

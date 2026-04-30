import { LanguageResponse } from '@/types'

function parseAcceptLanguage(header: string | null): string[] {
  if (!header) return []
  const items: { code: string; q: number }[] = []
  for (const part of header.split(',')) {
    const [tag, ...params] = part.trim().split(';')
    let q = 1
    for (const param of params) {
      const trimmed = param.trim()
      if (trimmed.startsWith('q=')) {
        const parsed = Number(trimmed.slice(2))
        if (!Number.isNaN(parsed)) q = parsed
      }
    }
    const code = tag.trim().toLowerCase().split('-')[0]
    if (!code || code === '*') continue
    items.push({ code, q })
  }
  items.sort((a, b) => b.q - a.q)
  const seen = new Set<string>()
  const out: string[] = []
  for (const { code } of items) {
    if (!seen.has(code)) {
      seen.add(code)
      out.push(code)
    }
  }
  return out
}

export function detectAcceptLanguage(header: string | null, catalog: LanguageResponse[]): string[] {
  const codes = parseAcceptLanguage(header)
  if (codes.length === 0) return []
  const matched: string[] = []
  for (const code of codes) {
    const found = catalog.find(
      (lang) => lang.iso_639_1?.toLowerCase() === code || lang.iso_639_3?.toLowerCase() === code,
    )
    if (found && !matched.includes(found.wikidata_id)) {
      matched.push(found.wikidata_id)
    }
  }
  return matched
}

import { notFound } from 'next/navigation'
import { cookies } from 'next/headers'
import { fetchWithAuth } from '@/lib/api-auth'
import { Politician } from '@/types'
import { PoliticianEvaluation } from './PoliticianEvaluation'
import { FILTER_LANGUAGES_COOKIE, deserializeFilterCookieValue } from '@/lib/cookies'

export default async function PoliticianPage({ params }: { params: Promise<{ qid: string }> }) {
  const { qid } = await params
  const cookieStore = await cookies()
  const languageQids = deserializeFilterCookieValue(cookieStore.get(FILTER_LANGUAGES_COOKIE)?.value)

  const searchParams = new URLSearchParams()
  for (const langQid of languageQids) {
    searchParams.append('languages', langQid)
  }
  const qs = searchParams.toString()
  const url = `${process.env.API_BASE_URL}/politicians/${qid}${qs ? `?${qs}` : ''}`

  const response = await fetchWithAuth(url)
  if (!response?.ok) notFound()

  const politician: Politician = await response.json()
  return <PoliticianEvaluation politician={politician} />
}

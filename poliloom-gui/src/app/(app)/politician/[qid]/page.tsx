import { notFound } from 'next/navigation'
import { fetchWithAuth } from '@/lib/api-auth'
import { getFilterLanguageQids } from '@/lib/filters'
import { Politician } from '@/types'
import { PoliticianEvaluation } from './PoliticianEvaluation'

export default async function PoliticianPage({ params }: { params: Promise<{ qid: string }> }) {
  const { qid } = await params
  const languageQids = (await getFilterLanguageQids()) ?? []

  const searchParams = new URLSearchParams()
  for (const langQid of languageQids) {
    searchParams.append('languages', langQid)
  }
  const qs = searchParams.toString()
  const url = `${process.env.API_BASE_URL}/politicians/${qid}${qs ? `?${qs}` : ''}`

  const response = await fetchWithAuth(url)
  if (response.status === 404) notFound()
  if (!response.ok) throw new Error(`Failed to fetch politician ${qid}: ${response.status}`)

  const politician: Politician = await response.json()
  return <PoliticianEvaluation politician={politician} />
}

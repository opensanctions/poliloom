import { notFound } from 'next/navigation'
import { fetchWithAuth } from '@/lib/api-auth'
import { Politician } from '@/types'
import { PoliticianEvaluation } from './PoliticianEvaluation'

export default async function PoliticianPage({ params }: { params: Promise<{ qid: string }> }) {
  const { qid } = await params
  const response = await fetchWithAuth(`${process.env.API_BASE_URL}/politicians/${qid}`)
  if (!response?.ok) notFound()

  const politician: Politician = await response.json()
  return <PoliticianEvaluation politician={politician} />
}

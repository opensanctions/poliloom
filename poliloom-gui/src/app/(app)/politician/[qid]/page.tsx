import { notFound } from 'next/navigation'
import { NextResponse } from 'next/server'
import { fetchWithAuth } from '@/lib/api-auth'
import { Politician } from '@/types'
import { PoliticianEvaluation } from './PoliticianEvaluation'

export default async function PoliticianPage({ params }: { params: Promise<{ qid: string }> }) {
  const { qid } = await params
  const apiBaseUrl = process.env.API_BASE_URL || 'http://localhost:8000'

  const response = await fetchWithAuth(`${apiBaseUrl}/politicians/${qid}`)

  if (response instanceof NextResponse || !response.ok) {
    notFound()
  }

  const politician: Politician = await response.json()

  return <PoliticianEvaluation politician={politician} />
}

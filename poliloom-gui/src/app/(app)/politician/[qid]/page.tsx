import { notFound } from 'next/navigation'
import { NextResponse } from 'next/server'
import { fetchWithAuth } from '@/lib/api-auth'
import { Politician } from '@/types'
import { PoliticianClient } from '@/components/evaluation/PoliticianClient'

export default async function PoliticianPage({ params }: { params: Promise<{ qid: string }> }) {
  const { qid } = await params
  const apiBaseUrl = process.env.API_BASE_URL || 'http://localhost:8000'

  const response = await fetchWithAuth(`${apiBaseUrl}/politicians/${qid}`)

  if (response instanceof NextResponse || !response.ok) {
    notFound()
  }

  const politician: Politician = await response.json()

  // Ensure all properties have key field set
  politician.properties = politician.properties.map((prop) => ({
    ...prop,
    key: prop.id || prop.key,
  }))

  return <PoliticianClient politician={politician} />
}

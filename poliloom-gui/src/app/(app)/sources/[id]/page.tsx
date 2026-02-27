import { notFound } from 'next/navigation'
import { NextResponse } from 'next/server'
import { fetchWithAuth } from '@/lib/api-auth'
import { SourceResponse } from '@/types'
import { SourceEvaluation } from './SourceEvaluation'

export default async function SourcePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const apiBaseUrl = process.env.API_BASE_URL || 'http://localhost:8000'

  const response = await fetchWithAuth(`${apiBaseUrl}/archived-pages/${id}`)

  if (response instanceof NextResponse || !response.ok) {
    notFound()
  }

  const source: SourceResponse = await response.json()

  // API properties always have id; set key (used for React keys and client-side lookups)
  source.politicians = source.politicians.map((politician) => ({
    ...politician,
    properties: politician.properties.map((prop) => ({
      ...prop,
      key: prop.id!,
    })),
  }))

  return <SourceEvaluation source={source} />
}

import { NextRequest } from 'next/server'
import { proxyToBackend } from '@/lib/api-auth'

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = await params
  return proxyToBackend(request, `/politicians/${resolvedParams.id}/properties`)
}

import { NextRequest } from 'next/server'
import { proxyToBackend } from '@/lib/api-auth'

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ preference_type: string }> },
) {
  const { preference_type } = await params
  return proxyToBackend(request, `/preferences/${preference_type}`)
}

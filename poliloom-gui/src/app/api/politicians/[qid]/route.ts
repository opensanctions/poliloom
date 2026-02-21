import { NextRequest } from 'next/server'
import { proxyToBackend } from '@/lib/api-auth'

export async function GET(request: NextRequest, { params }: { params: Promise<{ qid: string }> }) {
  const { qid } = await params
  return proxyToBackend(request, `/politicians/${qid}`)
}

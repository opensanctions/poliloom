import { NextRequest } from 'next/server'
import { proxyToBackend } from '@/lib/api-auth'

export async function GET(request: NextRequest) {
  return proxyToBackend(request, '/countries/search')
}

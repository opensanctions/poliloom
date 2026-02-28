import { NextRequest } from 'next/server'
import { proxyToBackend } from '@/lib/api-auth'

export async function POST(request: NextRequest) {
  return proxyToBackend(request, '/politicians')
}

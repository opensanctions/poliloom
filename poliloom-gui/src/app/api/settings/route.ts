import { NextRequest } from 'next/server'
import { proxyToBackend } from '@/lib/api-auth'

export async function GET(request: NextRequest) {
  return proxyToBackend(request, '/settings')
}

export async function PATCH(request: NextRequest) {
  return proxyToBackend(request, '/settings')
}

import { NextRequest } from 'next/server';
import { proxyToBackend } from '@/lib/api-auth';

export async function POST(
  request: NextRequest,
  { params }: { params: { preference_type: string } }
) {
  return proxyToBackend(request, `/preferences/${params.preference_type}`);
}
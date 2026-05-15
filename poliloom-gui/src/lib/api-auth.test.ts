import { describe, it, expect, vi, beforeEach } from 'vitest'
import { NextRequest, NextResponse } from 'next/server'

const mockHeadersGet = vi.fn<(name: string) => string | null>()
vi.mock('next/headers', () => ({
  headers: () => Promise.resolve({ get: mockHeadersGet }),
}))

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

import { fetchWithAuth, proxyToBackend } from './api-auth'

beforeEach(() => {
  mockHeadersGet.mockReset()
  mockFetch.mockReset()
})

describe('api-auth', () => {
  describe('fetchWithAuth', () => {
    it('throws when x-access-token header is missing (proxy.ts misconfigured)', async () => {
      mockHeadersGet.mockReturnValue(null)
      await expect(fetchWithAuth('http://backend/api/test')).rejects.toThrow(/x-access-token/)
      expect(mockFetch).not.toHaveBeenCalled()
    })

    it('forwards Authorization header from x-access-token', async () => {
      mockHeadersGet.mockReturnValue('my-token')
      mockFetch.mockResolvedValue(new Response('{}', { status: 200 }))

      await fetchWithAuth('http://backend/api/test')

      expect(mockHeadersGet).toHaveBeenCalledWith('x-access-token')
      expect(mockFetch).toHaveBeenCalledWith('http://backend/api/test', {
        headers: { Authorization: 'Bearer my-token' },
      })
    })

    it('merges provided headers with Authorization', async () => {
      mockHeadersGet.mockReturnValue('my-token')
      mockFetch.mockResolvedValue(new Response('{}', { status: 200 }))

      await fetchWithAuth('http://backend/api/test', {
        headers: { 'Content-Type': 'application/json' },
      })

      expect(mockFetch).toHaveBeenCalledWith('http://backend/api/test', {
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer my-token',
        },
      })
    })

    it('returns the raw backend response on non-OK status (caller decides)', async () => {
      mockHeadersGet.mockReturnValue('my-token')
      mockFetch.mockResolvedValue(new Response('', { status: 404, statusText: 'Not Found' }))

      const response = await fetchWithAuth('http://backend/api/test')

      expect(response.status).toBe(404)
      expect(response.ok).toBe(false)
    })

    it('returns the backend response on success', async () => {
      mockHeadersGet.mockReturnValue('my-token')
      mockFetch.mockResolvedValue(
        new Response('{"data": 1}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

      const response = await fetchWithAuth('http://backend/api/test')

      expect(response.status).toBe(200)
      const body = await response.json()
      expect(body).toEqual({ data: 1 })
    })
  })

  describe('proxyToBackend', () => {
    it('forwards GET request to backend with auth', async () => {
      mockHeadersGet.mockReturnValue('tok')
      mockFetch.mockResolvedValue(
        new Response('{"ok":true}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

      const request = new NextRequest('http://localhost:3000/api/test')
      const response = await proxyToBackend(request, '/api/v1/test')

      expect(mockFetch).toHaveBeenCalledWith(
        `${process.env.API_BASE_URL}/api/v1/test`,
        expect.objectContaining({ method: 'GET' }),
      )
      expect(response.status).toBe(200)
    })

    it('forwards query parameters', async () => {
      mockHeadersGet.mockReturnValue('tok')
      mockFetch.mockResolvedValue(
        new Response('{}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

      const request = new NextRequest('http://localhost:3000/api/test?page=2&limit=10')
      await proxyToBackend(request, '/api/v1/test')

      expect(mockFetch).toHaveBeenCalledWith(
        `${process.env.API_BASE_URL}/api/v1/test?page=2&limit=10`,
        expect.anything(),
      )
    })

    it('forwards body for POST requests', async () => {
      mockHeadersGet.mockReturnValue('tok')
      mockFetch.mockResolvedValue(
        new Response('{}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

      const request = new NextRequest('http://localhost:3000/api/test', {
        method: 'POST',
        body: JSON.stringify({ name: 'test' }),
        headers: { 'Content-Type': 'application/json' },
      })
      await proxyToBackend(request, '/api/v1/test')

      expect(mockFetch).toHaveBeenCalledWith(
        `${process.env.API_BASE_URL}/api/v1/test`,
        expect.objectContaining({
          method: 'POST',
          body: '{"name":"test"}',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        }),
      )
    })

    it('forwards body for PATCH requests', async () => {
      mockHeadersGet.mockReturnValue('tok')
      mockFetch.mockResolvedValue(
        new Response('{}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

      const request = new NextRequest('http://localhost:3000/api/test', {
        method: 'PATCH',
        body: JSON.stringify({ status: 'active' }),
        headers: { 'Content-Type': 'application/json' },
      })
      await proxyToBackend(request, '/api/v1/test')

      expect(mockFetch).toHaveBeenCalledWith(
        `${process.env.API_BASE_URL}/api/v1/test`,
        expect.objectContaining({
          method: 'PATCH',
          body: '{"status":"active"}',
        }),
      )
    })

    it('returns NextResponse error when backend returns non-OK', async () => {
      mockHeadersGet.mockReturnValue('tok')
      mockFetch.mockResolvedValue(new Response('', { status: 500, statusText: 'Server Error' }))

      const request = new NextRequest('http://localhost:3000/api/test')
      const response = await proxyToBackend(request, '/api/v1/test')

      expect(response).toBeInstanceOf(NextResponse)
      expect(response.status).toBe(500)
    })

    it('passes through Content-Type header from backend response', async () => {
      mockHeadersGet.mockReturnValue('tok')
      mockFetch.mockResolvedValue(
        new Response('<html></html>', {
          status: 200,
          headers: { 'Content-Type': 'text/html' },
        }),
      )

      const request = new NextRequest('http://localhost:3000/api/test')
      const response = await proxyToBackend(request, '/api/v1/test')

      expect(response.headers.get('Content-Type')).toBe('text/html')
    })
  })
})

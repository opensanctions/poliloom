import { describe, it, expect, vi, beforeEach } from 'vitest'
import { NextRequest, NextResponse } from 'next/server'

// Mock auth
const mockAuth = vi.fn()
vi.mock('@/auth', () => ({
  auth: () => mockAuth(),
}))

// Mock global fetch
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

import { fetchWithAuth, handleApiError, proxyToBackend } from './api-auth'

describe('api-auth', () => {
  describe('fetchWithAuth', () => {
    it('returns 401 when session has no access token', async () => {
      mockAuth.mockResolvedValue({ accessToken: null })

      const response = await fetchWithAuth('http://backend/api/test')

      expect(response).toBeInstanceOf(NextResponse)
      expect(response.status).toBe(401)
      const body = await response.json()
      expect(body.message).toBe('Not authenticated')
    })

    it('returns 401 when session is null', async () => {
      mockAuth.mockResolvedValue(null)

      const response = await fetchWithAuth('http://backend/api/test')

      expect(response.status).toBe(401)
    })

    it('returns 401 when session has error (token refresh failed)', async () => {
      mockAuth.mockResolvedValue({ accessToken: 'tok', error: 'RefreshError' })

      const response = await fetchWithAuth('http://backend/api/test')

      expect(response.status).toBe(401)
      const body = await response.json()
      expect(body.message).toBe('Token refresh failed')
    })

    it('forwards Authorization header to backend', async () => {
      mockAuth.mockResolvedValue({ accessToken: 'my-token' })
      mockFetch.mockResolvedValue(new Response('{}', { status: 200 }))

      await fetchWithAuth('http://backend/api/test')

      expect(mockFetch).toHaveBeenCalledWith('http://backend/api/test', {
        headers: {
          Authorization: 'Bearer my-token',
        },
      })
    })

    it('merges provided headers with Authorization', async () => {
      mockAuth.mockResolvedValue({ accessToken: 'my-token' })
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

    it('returns error response when backend returns non-ok status', async () => {
      mockAuth.mockResolvedValue({ accessToken: 'my-token' })
      mockFetch.mockResolvedValue(new Response('', { status: 404, statusText: 'Not Found' }))

      const response = await fetchWithAuth('http://backend/api/test')

      expect(response).toBeInstanceOf(NextResponse)
      expect(response.status).toBe(404)
      const body = await response.json()
      expect(body.message).toContain('Not Found')
    })

    it('returns the backend response on success', async () => {
      mockAuth.mockResolvedValue({ accessToken: 'my-token' })
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

  describe('handleApiError', () => {
    it('returns 500 with generic error message', () => {
      vi.spyOn(console, 'error').mockImplementation(() => {})
      const response = handleApiError(new Error('boom'), 'test-context')

      expect(response.status).toBe(500)
    })

    it('logs the error with context', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const error = new Error('boom')

      handleApiError(error, 'my-route')

      expect(consoleSpy).toHaveBeenCalledWith('Error in my-route:', error)
    })
  })

  describe('proxyToBackend', () => {
    it('forwards GET request to backend with auth', async () => {
      mockAuth.mockResolvedValue({ accessToken: 'tok' })
      mockFetch.mockResolvedValue(
        new Response('{"ok":true}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

      const request = new NextRequest('http://localhost:3000/api/test')
      const response = await proxyToBackend(request, '/api/v1/test')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/test',
        expect.objectContaining({ method: 'GET' }),
      )
      expect(response.status).toBe(200)
    })

    it('forwards query parameters', async () => {
      mockAuth.mockResolvedValue({ accessToken: 'tok' })
      mockFetch.mockResolvedValue(
        new Response('{}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

      const request = new NextRequest('http://localhost:3000/api/test?page=2&limit=10')
      await proxyToBackend(request, '/api/v1/test')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/test?page=2&limit=10',
        expect.anything(),
      )
    })

    it('forwards body for POST requests', async () => {
      mockAuth.mockResolvedValue({ accessToken: 'tok' })
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
        'http://localhost:8000/api/v1/test',
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
      mockAuth.mockResolvedValue({ accessToken: 'tok' })
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
        'http://localhost:8000/api/v1/test',
        expect.objectContaining({
          method: 'PATCH',
          body: '{"status":"active"}',
        }),
      )
    })

    it('returns auth error directly when not authenticated', async () => {
      mockAuth.mockResolvedValue({ accessToken: null })

      const request = new NextRequest('http://localhost:3000/api/test')
      const response = await proxyToBackend(request, '/api/v1/test')

      expect(response).toBeInstanceOf(NextResponse)
      expect(response.status).toBe(401)
      expect(mockFetch).not.toHaveBeenCalled()
    })

    it('passes through Content-Type header from backend response', async () => {
      mockAuth.mockResolvedValue({ accessToken: 'tok' })
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

    it('uses API_BASE_URL env var when set', async () => {
      process.env.API_BASE_URL = 'http://custom-backend:9000'
      mockAuth.mockResolvedValue({ accessToken: 'tok' })
      mockFetch.mockResolvedValue(
        new Response('{}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )

      const request = new NextRequest('http://localhost:3000/api/test')
      await proxyToBackend(request, '/api/v1/test')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://custom-backend:9000/api/v1/test',
        expect.anything(),
      )

      delete process.env.API_BASE_URL
    })
  })
})

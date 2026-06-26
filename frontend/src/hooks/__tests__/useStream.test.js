import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useStream } from '../useStream'

describe('useStream', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('initial state', () => {
    it('should have idle status initially', () => {
      const { result } = renderHook(() => useStream())

      expect(result.current.status).toBe('idle')
      expect(result.current.responseType).toBeNull()
      expect(result.current.statusMessage).toBe('')
      expect(result.current.tokens).toBe('')
      expect(result.current.error).toBeNull()
    })
  })

  describe('reset', () => {
    it('should reset all state to initial values', () => {
      const { result } = renderHook(() => useStream())

      act(() => {
        result.current.setStatus('streaming')
        result.current.setError('Some error')
        result.current.setStatusMessage('Processing...')
      })

      act(() => {
        result.current.reset()
      })

      expect(result.current.status).toBe('idle')
      expect(result.current.responseType).toBeNull()
      expect(result.current.statusMessage).toBe('')
      expect(result.current.tokens).toBe('')
      expect(result.current.error).toBeNull()
    })
  })

  describe('startStream', () => {
    it('should transition from idle to connecting', async () => {
      const { result } = renderHook(() => useStream())

      const mockResponse = new Response('data', {
        headers: { 'Content-Type': 'text/event-stream' }
      })

      const fetchFn = vi.fn().mockResolvedValue(mockResponse)

      act(() => {
        result.current.startStream(fetchFn)
      })

      await waitFor(() => {
        expect(result.current.status).toBe('connecting')
      })
    })

    it('should handle network errors', async () => {
      const { result } = renderHook(() => useStream())

      const fetchFn = vi.fn().mockRejectedValue(new Error('Network error'))

      await act(async () => {
        await result.current.startStream(fetchFn)
      })

      await waitFor(() => {
        expect(result.current.status).toBe('error')
        expect(result.current.error).toBe('Network error')
      })
    })

    it('should handle HTTP errors', async () => {
      const { result } = renderHook(() => useStream())

      const mockResponse = new Response(null, { status: 500 })
      const fetchFn = vi.fn().mockResolvedValue(mockResponse)

      await act(async () => {
        await result.current.startStream(fetchFn)
      })

      await waitFor(() => {
        expect(result.current.status).toBe('error')
      })
    })

    it('should surface the server detail message instead of a generic status string', async () => {
      const { result } = renderHook(() => useStream())

      const mockResponse = new Response(
        JSON.stringify({ detail: 'Message limit exceeded for this session' }),
        { status: 429 }
      )
      const fetchFn = vi.fn().mockResolvedValue(mockResponse)

      await act(async () => {
        await result.current.startStream(fetchFn)
      })

      await waitFor(() => {
        expect(result.current.error).toBe('Message limit exceeded for this session')
      })
    })

    it('should fall back to a generic status message when the error body is not JSON', async () => {
      const { result } = renderHook(() => useStream())

      const mockResponse = new Response('not json', { status: 503 })
      const fetchFn = vi.fn().mockResolvedValue(mockResponse)

      await act(async () => {
        await result.current.startStream(fetchFn)
      })

      await waitFor(() => {
        expect(result.current.error).toBe('Request failed: 503')
      })
    })
  })

  describe('SSE parsing', () => {
    const createMockStream = (chunks) => {
      const encoder = new TextEncoder()
      const stream = new ReadableStream({
        start(controller) {
          chunks.forEach(chunk => controller.enqueue(encoder.encode(chunk)))
          controller.close()
        }
      })
      return new Response(stream, {
        headers: { 'Content-Type': 'text/event-stream' }
      })
    }

    it('should parse start event', async () => {
      const { result } = renderHook(() => useStream())

      const mockResponse = createMockStream([
        'event: start\n',
        'data: {"type":"start","response_type":"chat"}\n\n'
      ])

      const fetchFn = vi.fn().mockResolvedValue(mockResponse)

      await act(async () => {
        await result.current.startStream(fetchFn)
      })

      await waitFor(() => {
        expect(result.current.responseType).toBe('chat')
      })
    })

    it('should parse status event', async () => {
      const { result } = renderHook(() => useStream())

      const mockResponse = createMockStream([
        'event: status\n',
        'data: {"type":"status","message":"Retrieving..."}\n\n'
      ])

      const fetchFn = vi.fn().mockResolvedValue(mockResponse)

      await act(async () => {
        await result.current.startStream(fetchFn)
      })

      await waitFor(() => {
        expect(result.current.statusMessage).toBe('Retrieving...')
      })
    })

    it('should accumulate token events', async () => {
      const { result } = renderHook(() => useStream())

      const mockResponse = createMockStream([
        'event: token\n',
        'data: {"type":"token","data":"Hello"}\n\n',
        'event: token\n',
        'data: {"type":"token","data":" world"}\n\n'
      ])

      const fetchFn = vi.fn().mockResolvedValue(mockResponse)

      await act(async () => {
        await result.current.startStream(fetchFn)
      })

      await waitFor(() => {
        expect(result.current.tokens).toBe('Hello world')
      })
    })

    it('should set complete status on done event', async () => {
      const { result } = renderHook(() => useStream())

      const mockResponse = createMockStream([
        'event: done\n',
        'data: {"type":"done"}\n\n'
      ])

      const fetchFn = vi.fn().mockResolvedValue(mockResponse)

      await act(async () => {
        await result.current.startStream(fetchFn)
      })

      await waitFor(() => {
        expect(result.current.status).toBe('complete')
      })
    })

    it('should handle error event', async () => {
      const { result } = renderHook(() => useStream())

      const mockResponse = createMockStream([
        'event: error\n',
        'data: {"type":"error","code":500,"message":"Server error"}\n\n'
      ])

      const fetchFn = vi.fn().mockResolvedValue(mockResponse)

      await act(async () => {
        await result.current.startStream(fetchFn)
      })

      await waitFor(() => {
        expect(result.current.status).toBe('error')
        expect(result.current.error).toBe('Server error')
      })
    })

    it('should skip malformed SSE lines', async () => {
      const { result } = renderHook(() => useStream())

      const mockResponse = createMockStream([
        'event: token\n',
        'data: {invalid json}\n\n',
        'event: token\n',
        'data: {"type":"token","data":"Valid"}\n\n'
      ])

      const fetchFn = vi.fn().mockResolvedValue(mockResponse)

      await act(async () => {
        await result.current.startStream(fetchFn)
      })

      await waitFor(() => {
        expect(result.current.tokens).toBe('Valid')
      })
    })
  })

  describe('abort', () => {
    it('should abort ongoing stream', async () => {
      const { result } = renderHook(() => useStream())

      const mockResponse = new Response(
        new ReadableStream({
          start(controller) {
            setTimeout(() => controller.close(), 5000)
          }
        }),
        { headers: { 'Content-Type': 'text/event-stream' } }
      )

      const fetchFn = vi.fn().mockResolvedValue(mockResponse)

      act(() => {
        result.current.startStream(fetchFn)
      })

      await waitFor(() => {
        expect(result.current.status).toBe('streaming')
      })

      act(() => {
        result.current.abort()
      })

      expect(result.current.status).toBe('idle')
    })
  })
})

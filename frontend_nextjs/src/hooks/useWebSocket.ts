'use client'

import { useEffect, useRef, useCallback } from 'react'
import { API_BASE } from '@/lib/api'

export function useWebSocket(path: string, onMessage: (data: unknown) => void) {
  const wsRef = useRef<WebSocket | null>(null)
  const wsUrl = API_BASE.replace('http', 'ws') + path

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  useEffect(() => {
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws
    ws.onmessage = (e) => onMessage(JSON.parse(e.data))
    ws.onerror = (e) => console.error('WS error', e)
    return () => ws.close()
  }, [wsUrl, onMessage])

  return { send }
}

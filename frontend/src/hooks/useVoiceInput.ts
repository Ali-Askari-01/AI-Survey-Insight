'use client'

import { useCallback, useRef, useState } from 'react'
import { API_BASE } from '@/lib/api'

export function useVoiceInput(sessionId?: string, questionId?: number) {
  const [recording, setRecording] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])

  const start = useCallback(async () => {
    setError(null)
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const recorder = new MediaRecorder(stream)
    chunksRef.current = []
    recorder.ondataavailable = (e) => chunksRef.current.push(e.data)
    recorder.start()
    mediaRecorderRef.current = recorder
    setRecording(true)
  }, [])

  const stopAndTranscribe = useCallback(async () => {
    const recorder = mediaRecorderRef.current
    if (!recorder) return null

    setLoading(true)
    const data = await new Promise<Blob | null>((resolve) => {
      recorder.onstop = () => {
        resolve(new Blob(chunksRef.current, { type: 'audio/webm' }))
      }
      recorder.stop()
      recorder.stream.getTracks().forEach((t) => t.stop())
      setRecording(false)
    })

    if (!data) {
      setLoading(false)
      return null
    }

    try {
      const form = new FormData()
      form.append('audio', data, 'recording.webm')

      const endpoint = sessionId && questionId
        ? `${API_BASE}/api/interviews/transcribe-and-respond?session_id=${encodeURIComponent(sessionId)}&question_id=${questionId}`
        : `${API_BASE}/api/interviews/transcribe`

      const res = await fetch(endpoint, { method: 'POST', body: form })
      if (!res.ok) throw new Error(`Transcription failed: ${res.status}`)
      return await res.json()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Voice transcription failed')
      return null
    } finally {
      setLoading(false)
    }
  }, [sessionId, questionId])

  return { recording, loading, error, start, stopAndTranscribe }
}

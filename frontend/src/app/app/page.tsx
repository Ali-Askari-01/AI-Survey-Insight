'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { apiFetch } from '@/lib/api'
import { clientApi } from '@/lib/clientApi'

export default function AuthPage() {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const router = useRouter()
  const searchParams = useSearchParams()

  useEffect(() => {
    const googleToken = searchParams.get('google_token')
    const authError = searchParams.get('auth_error')

    if (authError) {
      setError(`Google sign-in failed: ${authError}`)
      return
    }

    if (googleToken && typeof window !== 'undefined') {
      localStorage.setItem('token', googleToken)
      clientApi.setToken(googleToken)
      router.replace('/app/dashboard')
    }
  }, [searchParams, router])

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setLoading(true)
    setError('')
    const data = Object.fromEntries(new FormData(e.currentTarget))
    try {
      const endpoint = mode === 'signin' ? '/api/auth/login' : '/api/auth/register'
      const result = await apiFetch(endpoint, { method: 'POST', body: JSON.stringify(data) })

      if (typeof window !== 'undefined' && result?.access_token) {
        localStorage.setItem('token', result.access_token)
        clientApi.setToken(result.access_token)
      }

      router.push('/app/dashboard')
    } catch {
      setError('Authentication failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4 py-8 bg-bg"
      style={{
        backgroundImage:
          'radial-gradient(ellipse at 15% 40%, rgba(124,58,237,0.18) 0%, transparent 55%), radial-gradient(ellipse at 85% 15%, rgba(0,229,255,0.1) 0%, transparent 45%)',
      }}
    >
      <div className="w-full max-w-md">
        <div className="relative bg-surface/95 border border-white/[0.08] rounded-3xl p-8 sm:p-10 shadow-[0_0_0_1px_rgba(0,229,255,0.05),0_24px_60px_rgba(0,0,0,0.7),0_0_80px_rgba(124,58,237,0.1)]">
          <div
            className="absolute top-0 left-0 right-0 h-px rounded-t-3xl"
            style={{
              background:
                'linear-gradient(90deg, transparent, rgba(0,229,255,0.5) 30%, rgba(124,58,237,0.5) 70%, transparent)',
            }}
          />

          <div className="text-center mb-8">
            <h1 className="font-display text-3xl font-black bg-gradient-accent bg-clip-text text-transparent">InsightAI</h1>
            <p className="text-text-muted text-sm mt-2">Multi-Channel AI Feedback & Insight Engine</p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {mode === 'signup' && <Input name="name" label="Full Name" placeholder="Your name" required />}
            <Input name="email" type="email" label="Email" placeholder="you@company.com" required />
            <Input
              name="password"
              type="password"
              label="Password"
              placeholder="••••••••"
              hint={mode === 'signup' ? 'Min 8 chars · 1 uppercase · 1 lowercase · 1 number' : undefined}
              required
            />

            {error && <p className="text-sm text-red-400 text-center">{error}</p>}

            <Button type="submit" size="lg" loading={loading} className="w-full mt-2">
              {mode === 'signin' ? 'Sign In' : 'Create Account'}
            </Button>
          </form>

          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-white/[0.07]" />
            <span className="text-xs text-text-subtle uppercase tracking-widest">or</span>
            <div className="flex-1 h-px bg-white/[0.07]" />
          </div>

          <a
            href={`${process.env.NEXT_PUBLIC_API_URL || ''}/api/auth/google/login`}
            className="w-full flex items-center justify-center gap-3 bg-white/[0.05] border border-white/10 rounded-xl py-3.5 text-sm font-medium text-text-primary hover:bg-white/[0.08] hover:border-white/20 transition-all min-h-[48px]"
          >
            <svg viewBox="0 0 24 24" className="w-5 h-5 shrink-0">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            Continue with Google
          </a>

          <p className="text-center text-sm text-text-muted mt-6">
            {mode === 'signin' ? "Don't have an account? " : 'Already have an account? '}
            <button
              onClick={() => {
                setMode((m) => (m === 'signin' ? 'signup' : 'signin'))
                setError('')
              }}
              className="text-accent-cyan font-medium hover:opacity-75 transition-opacity"
            >
              {mode === 'signin' ? 'Create one' : 'Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}

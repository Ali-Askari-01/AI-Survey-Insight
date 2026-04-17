'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { AppLayout } from '@/components/layout/AppLayout'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { clientApi } from '@/lib/clientApi'
import { API_BASE } from '@/lib/api'
import { Copy, ExternalLink, Plus, RefreshCcw, Trash2 } from 'lucide-react'

type SurveyItem = {
  id: number
  title?: string
  description?: string
  status?: string
  created_at?: string
  total_responses?: number
  question_count?: number
  publication?: {
    share_code?: string
    status?: string
  } | null
  links?: {
    web_form?: string
    chat?: string
    audio?: string
    landing?: string
  } | null
}

function formatDate(value?: string) {
  if (!value) return 'Unknown date'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown date'
  return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', year: 'numeric' }).format(date)
}

function normalizeStatus(status?: string) {
  const s = (status || 'draft').toLowerCase()
  if (s === 'active') return { label: 'Active', variant: 'green' as const }
  if (s === 'paused') return { label: 'Paused', variant: 'gold' as const }
  if (s === 'closed') return { label: 'Closed', variant: 'muted' as const }
  return { label: 'Draft', variant: 'purple' as const }
}

export default function SurveysPage() {
  const [surveys, setSurveys] = useState<SurveyItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actioningId, setActioningId] = useState<number | null>(null)

  const fullLinkBase = useMemo(() => API_BASE.replace(/\/$/, ''), [])

  const loadSurveys = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await clientApi.publish.mySurveys()
      setSurveys(Array.isArray(data) ? (data as SurveyItem[]) : [])
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load surveys'
      setError(msg)
      setSurveys([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadSurveys()
  }, [loadSurveys])

  async function publishSurvey(survey: SurveyItem) {
    setActioningId(survey.id)
    setError('')
    try {
      await clientApi.publish.publish({
        survey_id: survey.id,
        title: survey.title,
        description: survey.description,
        web_form_enabled: true,
        chat_enabled: true,
        audio_enabled: true,
        require_email: true,
      })
      await loadSurveys()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to publish survey')
    } finally {
      setActioningId(null)
    }
  }

  async function deleteSurvey(surveyId: number) {
    const ok = window.confirm('Delete this survey permanently? This cannot be undone.')
    if (!ok) return

    setActioningId(surveyId)
    setError('')
    try {
      await clientApi.surveys.deleteSurvey(surveyId)
      setSurveys((prev) => prev.filter((s) => s.id !== surveyId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete survey')
    } finally {
      setActioningId(null)
    }
  }

  async function copyLandingLink(path?: string) {
    if (!path) return
    const full = `${fullLinkBase}${path}`
    try {
      await navigator.clipboard.writeText(full)
    } catch {
      setError('Unable to copy link. Please copy manually.')
    }
  }

  return (
    <AppLayout>
      <div className="space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h1 className="font-display text-3xl md:text-4xl font-bold">My Surveys</h1>
            <p className="text-text-muted mt-1">Manage, publish, and review all survey activity.</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={loadSurveys}>
              <RefreshCcw size={16} className="mr-1.5" />
              Refresh
            </Button>
            <Link href="/app/designer">
              <Button size="sm">
                <Plus size={16} className="mr-1.5" />
                New Survey
              </Button>
            </Link>
          </div>
        </div>

        {error ? (
          <Card className="p-4 border-red-500/30 bg-red-500/5">
            <p className="text-sm text-red-300">{error}</p>
          </Card>
        ) : null}

        {loading ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="p-5 animate-pulse"><div className="h-5 bg-white/10 rounded w-1/3" /><div className="h-4 bg-white/10 rounded w-full mt-3" /><div className="h-4 bg-white/10 rounded w-2/3 mt-2" /></Card>
            <Card className="p-5 animate-pulse"><div className="h-5 bg-white/10 rounded w-1/3" /><div className="h-4 bg-white/10 rounded w-full mt-3" /><div className="h-4 bg-white/10 rounded w-2/3 mt-2" /></Card>
          </div>
        ) : null}

        {!loading && surveys.length === 0 ? (
          <Card glow className="p-8 text-center">
            <h2 className="font-display text-2xl font-bold">No surveys yet</h2>
            <p className="text-text-muted mt-2 max-w-xl mx-auto">
              Create your first AI-powered survey to start collecting responses and generating insights.
            </p>
            <div className="mt-5">
              <Link href="/app/designer">
                <Button size="lg">Create First Survey</Button>
              </Link>
            </div>
          </Card>
        ) : null}

        {!loading && surveys.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {surveys.map((survey) => {
              const status = normalizeStatus(survey.publication?.status || survey.status)
              const isPublished = Boolean(survey.publication?.share_code)

              return (
                <Card key={survey.id} className="p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold text-lg leading-tight">{survey.title || 'Untitled Survey'}</h3>
                      <p className="text-xs text-text-subtle mt-1">Created {formatDate(survey.created_at)}</p>
                    </div>
                    <Badge variant={status.variant}>{status.label}</Badge>
                  </div>

                  <p className="text-sm text-text-muted mt-3 line-clamp-2">
                    {survey.description || 'No description provided for this survey.'}
                  </p>

                  <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                    <div className="rounded-xl bg-white/[0.03] border border-white/10 py-2">
                      <p className="text-lg font-semibold">{survey.question_count || 0}</p>
                      <p className="text-[11px] text-text-subtle">Questions</p>
                    </div>
                    <div className="rounded-xl bg-white/[0.03] border border-white/10 py-2">
                      <p className="text-lg font-semibold">{survey.total_responses || 0}</p>
                      <p className="text-[11px] text-text-subtle">Responses</p>
                    </div>
                    <div className="rounded-xl bg-white/[0.03] border border-white/10 py-2">
                      <p className="text-lg font-semibold">{isPublished ? 'Live' : 'Draft'}</p>
                      <p className="text-[11px] text-text-subtle">State</p>
                    </div>
                  </div>

                  {survey.links?.landing ? (
                    <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.03] p-3">
                      <p className="text-xs text-text-subtle truncate">{`${fullLinkBase}${survey.links.landing}`}</p>
                      <div className="mt-2 flex items-center gap-2">
                        <Button
                          size="sm"
                          variant="secondary"
                          className="flex-1"
                          onClick={() => copyLandingLink(survey.links?.landing)}
                        >
                          <Copy size={14} className="mr-1.5" />
                          Copy Link
                        </Button>
                        <a
                          href={`${fullLinkBase}${survey.links.landing}`}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex"
                        >
                          <Button size="sm" variant="ghost">
                            <ExternalLink size={14} className="mr-1.5" />
                            Open
                          </Button>
                        </a>
                      </div>
                    </div>
                  ) : null}

                  <div className="mt-4 flex flex-wrap gap-2">
                    {!isPublished ? (
                      <Button
                        size="sm"
                        onClick={() => publishSurvey(survey)}
                        loading={actioningId === survey.id}
                      >
                        Publish
                      </Button>
                    ) : null}

                    <Link href="/app/insights">
                      <Button size="sm" variant="secondary">View Insights</Button>
                    </Link>

                    <Link href="/app/reports">
                      <Button size="sm" variant="secondary">View Reports</Button>
                    </Link>

                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => deleteSurvey(survey.id)}
                      loading={actioningId === survey.id}
                    >
                      <Trash2 size={14} className="mr-1.5" />
                      Delete
                    </Button>
                  </div>
                </Card>
              )
            })}
          </div>
        ) : null}
      </div>
    </AppLayout>
  )
}

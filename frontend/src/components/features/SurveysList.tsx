'use client'

import { useEffect, useState } from 'react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/Dialog'
import { Input } from '@/components/ui/Input'
import { clientApi } from '@/lib/clientApi'
import { Plus, Edit2, Trash2, Play, Archive, Sparkles } from 'lucide-react'

interface Survey {
  id?: string
  title: string
  goal?: string
  status: 'draft' | 'active' | 'paused' | 'closed'
  response_count?: number
  created_at?: string
  updated_at?: string
  expected_duration?: number
}

export default function SurveysList() {
  const [surveys, setSurveys] = useState<Survey[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [formData, setFormData] = useState({ title: '', goal: '', duration: 15 })
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    fetchSurveys()
  }, [])

  async function fetchSurveys() {
    try {
      setLoading(true)
      const data = await clientApi.get('/api/surveys')
      setSurveys(data?.surveys || [])
      setError('')
    } catch (err) {
      setError('Failed to load surveys')
      console.error(err)
      setSurveys([])
    } finally {
      setLoading(false)
    }
  }

  async function handleCreateSurvey(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setIsSubmitting(true)
    try {
      const newSurvey = await clientApi.post('/api/surveys', {
        title: formData.title,
        goal: formData.goal,
        expected_duration: formData.duration,
        status: 'draft',
      })
      setSurveys([...surveys, newSurvey])
      setFormData({ title: '', goal: '', duration: 15 })
      setIsCreateDialogOpen(false)
    } catch (err) {
      setError('Failed to create survey')
      console.error(err)
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleDeleteSurvey(id: string | undefined) {
    if (!id || !confirm('Delete this survey? This cannot be undone.')) return
    try {
      await clientApi.delete(`/api/surveys/${id}`)
      setSurveys(surveys.filter(s => s.id !== id))
    } catch (err) {
      setError('Failed to delete survey')
      console.error(err)
    }
  }

  async function handleStatusChange(id: string | undefined, newStatus: Survey['status']) {
    if (!id) return
    try {
      const updated = await clientApi.put(`/api/surveys/${id}`, { status: newStatus })
      setSurveys(surveys.map(s => (s.id === id ? updated : s)))
    } catch (err) {
      setError('Failed to update survey')
      console.error(err)
    }
  }

  const getStatusColor = (status: Survey['status']) => {
    return {
      active: 'green',
      draft: 'muted',
      paused: 'gold',
      closed: 'purple',
    }[status] as any
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-text-muted">Loading surveys...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">My Surveys</h1>
          <p className="text-text-muted mt-2">
            {surveys.length} survey{surveys.length !== 1 ? 's' : ''} · Manage, publish, and review all survey activity.
          </p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)} size="lg" className="w-full sm:w-auto">
          <Plus className="mr-2" size={18} />
          New Survey
        </Button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm">{error}</div>
      )}

      {/* Surveys Grid */}
      {surveys.length === 0 ? (
        <Card className="relative overflow-hidden p-10 sm:p-12 text-center border border-accent-cyan/20 bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.14),transparent_58%),linear-gradient(180deg,rgba(255,255,255,0.03),rgba(255,255,255,0))]">
          <div className="mx-auto mb-4 w-11 h-11 rounded-xl bg-accent-cyan/15 border border-accent-cyan/35 flex items-center justify-center text-accent-cyan">
            <Sparkles size={18} />
          </div>
          <div className="text-text-primary text-lg font-semibold mb-2">Your workspace is clean and ready</div>
          <p className="text-sm text-text-subtle mb-6 max-w-md mx-auto">
            Start with one focused survey, publish it in minutes, and collect meaningful responses without setup friction.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2 mb-7 text-xs text-text-muted">
            <span className="px-3 py-1 rounded-full border border-white/10 bg-white/[0.03]">Fast setup</span>
            <span className="px-3 py-1 rounded-full border border-white/10 bg-white/[0.03]">AI-ready prompts</span>
            <span className="px-3 py-1 rounded-full border border-white/10 bg-white/[0.03]">Real-time analytics</span>
          </div>
          <Button onClick={() => setIsCreateDialogOpen(true)}>
            <Plus className="mr-2" size={16} />
            Create Your First Survey
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {surveys.map(survey => (
            <Card key={survey.id} className="p-5 flex flex-col hover:border-accent-cyan/40 transition-all">
              {/* Title & Status */}
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold truncate text-base text-text-primary">{survey.title}</h3>
                  {survey.goal && (
                    <p className="text-xs text-text-subtle mt-1 line-clamp-2">{survey.goal}</p>
                  )}
                </div>
                <Badge variant={getStatusColor(survey.status)}>{survey.status}</Badge>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-2 my-4 py-3 border-y border-white/[0.07]">
                <div>
                  <p className="text-xs text-text-subtle">Responses</p>
                  <p className="text-lg font-bold text-accent-cyan">{survey.response_count || 0}</p>
                </div>
                <div>
                  <p className="text-xs text-text-subtle">Duration</p>
                  <p className="text-lg font-bold text-accent-purple">{survey.expected_duration || '--'} min</p>
                </div>
              </div>

              {/* Meta */}
              <p className="text-xs text-text-subtle mb-4">
                Created {new Date(survey.created_at || Date.now()).toLocaleDateString()}
              </p>

              {/* Actions */}
              <div className="flex gap-2 mt-auto">
                {survey.status === 'draft' && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => handleStatusChange(survey.id, 'active')}
                    className="flex-1"
                  >
                    <Play size={14} className="mr-1" />
                    Launch
                  </Button>
                )}

                {survey.status === 'active' && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => handleStatusChange(survey.id, 'paused')}
                    className="flex-1"
                  >
                    <Archive size={14} className="mr-1" />
                    Pause
                  </Button>
                )}

                <button
                  onClick={() => {
                    /* navigate to survey detail/edit */
                  }}
                  className="flex-1 flex items-center justify-center text-xs font-medium px-3 py-2 rounded-lg
                             bg-white/[0.04] text-text-muted hover:text-text-primary hover:bg-white/[0.06]
                             transition-all"
                  title="Edit survey"
                >
                  <Edit2 size={14} />
                </button>

                <button
                  onClick={() => handleDeleteSurvey(survey.id)}
                  className="flex items-center justify-center text-xs font-medium px-3 py-2 rounded-lg
                             bg-red-500/10 text-red-400 hover:bg-red-500/20
                             transition-all"
                  title="Delete survey"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create Survey Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Survey</DialogTitle>
            <DialogDescription>Start by naming your survey and describing its goal</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateSurvey} className="space-y-4">
            <Input
              label="Survey Title"
              placeholder="e.g., Q2 Customer Feedback"
              value={formData.title}
              onChange={e => setFormData({ ...formData, title: e.target.value })}
              required
            />
            <Input
              label="Survey Goal (optional)"
              placeholder="What do you want to learn from this survey?"
              value={formData.goal}
              onChange={e => setFormData({ ...formData, goal: e.target.value })}
            />
            <div>
              <label className="text-sm font-medium text-text-muted block mb-2">Expected Duration (minutes)</label>
              <select
                value={formData.duration}
                onChange={e => setFormData({ ...formData, duration: parseInt(e.target.value) })}
                className="w-full bg-white/[0.04] border border-white/10 rounded-xl px-4 py-3
                           text-text-primary outline-none focus:border-accent-cyan/40"
              >
                <option value={5}>5 minutes</option>
                <option value={10}>10 minutes</option>
                <option value={15}>15 minutes (recommended)</option>
                <option value={20}>20 minutes</option>
                <option value={30}>30 minutes</option>
              </select>
            </div>
            <div className="flex gap-3 pt-4">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setIsCreateDialogOpen(false)}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button type="submit" loading={isSubmitting} className="flex-1">
                Create Survey
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}

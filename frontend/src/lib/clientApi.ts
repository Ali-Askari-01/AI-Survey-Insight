'use client'

import { API_BASE } from '@/lib/api'

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

class ClientAPI {
  private token: string | null = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null

  setToken(token: string | null) {
    this.token = token
    if (typeof window === 'undefined') return
    if (token) localStorage.setItem('auth_token', token)
    else localStorage.removeItem('auth_token')
  }

  getToken() {
    return this.token
  }

  private async request(method: HttpMethod, endpoint: string, data?: unknown, isForm = false) {
    const headers: Record<string, string> = {}
    if (!isForm) headers['Content-Type'] = 'application/json'
    if (this.token) headers.Authorization = `Bearer ${this.token}`

    const res = await fetch(`${API_BASE}${endpoint}`, {
      method,
      headers,
      body: data
        ? isForm
          ? (data as BodyInit)
          : JSON.stringify(data)
        : undefined,
    })

    if (!res.ok) {
      if (res.status === 401) this.setToken(null)
      let detail = `HTTP ${res.status}`
      try {
        const err = await res.json()
        detail = err?.detail || detail
      } catch {
        // ignore parse errors
      }
      throw new Error(detail)
    }

    return res.json()
  }

  get(endpoint: string) { return this.request('GET', endpoint) }
  post(endpoint: string, data?: unknown) { return this.request('POST', endpoint, data) }
  put(endpoint: string, data?: unknown) { return this.request('PUT', endpoint, data) }
  delete(endpoint: string) { return this.request('DELETE', endpoint) }

  auth = {
    register: (name: string, email: string, password: string) => this.post('/api/auth/register', { name, email, password }),
    login: (email: string, password: string) => this.post('/api/auth/login', { email, password }),
    me: () => this.get('/api/auth/me'),
    listUsers: () => this.get('/api/auth/users'),
    updateRole: (userId: number | string, role: string) => this.put(`/api/auth/users/${userId}/role`, { role }),
  }

  surveys = {
    list: () => this.get('/api/surveys/'),
    get: (id: number | string) => this.get(`/api/surveys/${id}`),
    create: (data: unknown) => this.post('/api/surveys/', data),
    getFlow: (id: number | string) => this.get(`/api/surveys/${id}/flow`),
    createQuestion: (data: unknown) => this.post('/api/surveys/questions', data),
    updateQuestion: (id: number | string, data: unknown) => this.put(`/api/surveys/questions/${id}`, data),
    deleteQuestion: (id: number | string) => this.delete(`/api/surveys/questions/${id}`),
    reorderQuestions: (orders: unknown) => this.post('/api/surveys/questions/reorder', { orders }),
    parseGoal: (input: string) => this.post('/api/surveys/goals/ai-parse', { user_input: input }),
    generateQuestions: (goalId: number | string, count: number) => this.post('/api/surveys/questions/ai-generate', { research_goal_id: goalId, count }),
    generateDeepQuestions: (goalText: string, researchType: string, count: number) =>
      this.post('/api/surveys/questions/ai-generate-deep', { goal_text: goalText, research_type: researchType, count }),
    intakeClarify: (message: string, conversation: unknown[]) => this.post('/api/surveys/intake/clarify', { message, conversation }),
    generateAudienceTargeted: (goalText: string, targetAudiences: string[], researchType: string, countPerAudience: number) =>
      this.post('/api/surveys/questions/ai-generate-audience-targeted', {
        goal_text: goalText,
        target_audiences: targetAudiences,
        research_type: researchType,
        count_per_audience: countPerAudience,
      }),
    generateConsent: (title: string, goal: string) => this.post('/api/surveys/generate-consent', { title, goal }),
    getTemplates: () => this.get('/api/surveys/templates'),
    deleteSurvey: (id: number | string) => this.delete(`/api/surveys/${id}`),
    listGoals: () => this.get('/api/surveys/goals'),
    getGoal: (id: number | string) => this.get(`/api/surveys/goals/${id}`),
    createGoal: (data: unknown) => this.post('/api/surveys/goals', data),
  }

  interviews = {
    createSession: (data: unknown) => this.post('/api/interviews/sessions', data),
    getSession: (id: number | string) => this.get(`/api/interviews/sessions/${id}`),
    resumeSession: (id: number | string) => this.post(`/api/interviews/sessions/${id}/resume`),
    respond: (data: unknown) => this.post('/api/interviews/respond', data),
    chat: (data: unknown) => this.post('/api/interviews/chat', data),
    getHistory: (sessionId: number | string) => this.get(`/api/interviews/sessions/${sessionId}/history`),
    completeInterview: (sessionId: number | string) => this.post(`/api/interviews/sessions/${sessionId}/complete`),
    getMetrics: (surveyId: number | string) => this.get(`/api/interviews/metrics/${surveyId}`),
    transcribe: async (audioBlob: Blob, filename = 'recording.webm') => {
      const formData = new FormData()
      formData.append('file', audioBlob, filename)
      return this.request('POST', '/api/interviews/transcribe', formData, true)
    },
    transcribeAndRespond: async (audioBlob: Blob, sessionId: string, questionId: number, filename = 'recording.webm') => {
      const formData = new FormData()
      formData.append('file', audioBlob, filename)
      const url = `/api/interviews/transcribe-and-respond?session_id=${encodeURIComponent(sessionId)}&question_id=${questionId}`
      return this.request('POST', url, formData, true)
    },
  }

  insights = {
    get: (surveyId: number | string, filters: Record<string, string | number | undefined> = {}) => {
      const params = new URLSearchParams()
      Object.entries(filters).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') params.append(k, String(v))
      })
      const qs = params.toString()
      return this.get(`/api/insights/${surveyId}${qs ? `?${qs}` : ''}`)
    },
    getSummary: (surveyId: number | string) => this.get(`/api/insights/${surveyId}/summary`),
    getThemes: (surveyId: number | string) => this.get(`/api/insights/themes/${surveyId}`),
    getBubbleData: (surveyId: number | string) => this.get(`/api/insights/themes/${surveyId}/bubble-data`),
    getBubbles: (surveyId: number | string) => this.get(`/api/insights/themes/${surveyId}/bubble-data`),
    getSentiment: (surveyId: number | string) => this.get(`/api/insights/sentiment/${surveyId}`),
    getHeatmap: (surveyId: number | string) => this.get(`/api/insights/sentiment/${surveyId}/heatmap`),
    getTrends: (surveyId: number | string) => this.get(`/api/insights/sentiment/${surveyId}/trends`),
    getPatterns: (surveyId: number | string) => this.get(`/api/insights/patterns/${surveyId}`),
    getStory: (surveyId: number | string) => this.get(`/api/insights/${surveyId}/story`),
    chatQuery: (surveyId: number | string, message: string, conversationId: string | null = null, persona = 'analyst') =>
      this.post(`/api/insights/${surveyId}/chat`, { message, conversation_id: conversationId, persona }),
    chatHistory: (surveyId: number | string, conversationId: string) =>
      this.get(`/api/insights/${surveyId}/chat/history?conversation_id=${encodeURIComponent(conversationId)}`),
    chatConversations: (surveyId: number | string) => this.get(`/api/insights/${surveyId}/chat/conversations`),
    createAnnotation: (surveyId: number | string, data: unknown) => this.post(`/api/insights/${surveyId}/annotations`, data),
    getAnnotations: (surveyId: number | string, targetType?: string, targetId?: string | number) => {
      const params = new URLSearchParams()
      if (targetType) params.append('target_type', targetType)
      if (targetId !== undefined) params.append('target_id', String(targetId))
      const qs = params.toString()
      return this.get(`/api/insights/${surveyId}/annotations${qs ? `?${qs}` : ''}`)
    },
    deleteAnnotation: (surveyId: number | string, annotationId: number | string) =>
      this.delete(`/api/insights/${surveyId}/annotations/${annotationId}`),
  }

  reports = {
    getSummary: (surveyId: number | string, tone = 'neutral', length = 'medium') =>
      this.get(`/api/reports/summary/${surveyId}?tone=${tone}&length=${length}`),
    generate: (data: unknown) => this.post('/api/reports/generate', data),
    list: (surveyId: number | string) => this.get(`/api/reports/${surveyId}`),
    getRecommendations: (surveyId: number | string, filters: Record<string, string | number | undefined> = {}) => {
      const params = new URLSearchParams()
      Object.entries(filters).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') params.append(k, String(v))
      })
      const qs = params.toString()
      return this.get(`/api/reports/recommendations/${surveyId}${qs ? `?${qs}` : ''}`)
    },
    getMatrix: (surveyId: number | string) => this.get(`/api/reports/recommendations/${surveyId}/matrix`),
    getRoadmap: (surveyId: number | string) => this.get(`/api/reports/recommendations/${surveyId}/roadmap`),
    exportCSV: (surveyId: number | string) => this.get(`/api/reports/export/${surveyId}/csv`),
    exportJira: (surveyId: number | string) => this.get(`/api/reports/export/${surveyId}/jira`),
  }

  notifications = {
    list: (filters: Record<string, string | number | boolean | undefined> = {}) => {
      const params = new URLSearchParams()
      Object.entries(filters).forEach(([k, v]) => {
        if (v !== undefined) params.append(k, String(v))
      })
      const qs = params.toString()
      return this.get(`/api/notifications/${qs ? `?${qs}` : ''}`)
    },
    getUnreadCount: () => this.get('/api/notifications/unread-count'),
    markRead: (id: number | string) => this.put(`/api/notifications/${id}/read`),
    markAllRead: () => this.put('/api/notifications/read-all'),
    create: (data: unknown) => this.post('/api/notifications/', data),
    delete: (id: number | string) => this.delete(`/api/notifications/${id}`),
    emailStatus: () => this.get('/api/notifications/email-status'),
    sendInvites: (surveyId: number | string, emails: string[]) => this.post('/api/notifications/send-invites', { survey_id: surveyId, emails }),
  }

  simulation = {
    run: (surveyId: number | string, persona: string | null = null, count = 1) =>
      this.post('/api/interviews/simulate', { survey_id: surveyId, persona, num_simulations: count }),
  }

  publish = {
    publish: (data: unknown) => this.post('/api/publish/', data),
    mySurveys: () => this.get('/api/publish/my-surveys'),
    getSurveyByCode: (code: string) => this.get(`/api/publish/s/${code}`),
    join: (data: unknown) => this.post('/api/publish/join', data),
    analytics: (surveyId: number | string) => this.get(`/api/publish/analytics/${surveyId}`),
    analysis: (surveyId: number | string) => this.get(`/api/publish/analysis/${surveyId}`),
    updateStatus: (shareCode: string, status: string) => this.put(`/api/publish/${shareCode}/status`, { status }),
    saveTranscript: (sessionId: number | string) => this.post(`/api/publish/transcripts/${sessionId}`),
    getTranscripts: (surveyId: number | string) => this.get(`/api/publish/transcripts/${surveyId}/all`),
    getSessionTranscript: (sessionId: number | string) => this.get(`/api/publish/transcripts/session/${sessionId}`),
    exportRespondentsCSV: (surveyId: number | string) => this.get(`/api/publish/export/${surveyId}/respondents-csv`),
    exportAnalysisCSV: (surveyId: number | string) => this.get(`/api/publish/export/${surveyId}/analysis-csv`),
    exportReportHTML: (surveyId: number | string) => this.get(`/api/publish/export/${surveyId}/report-html`),
  }
}

export const clientApi = new ClientAPI()

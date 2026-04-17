import { AppLayout } from '@/components/layout/AppLayout'
import InsightsDashboard from '@/components/features/InsightsDashboard'

export default function InsightsPage() {
  return (
    <AppLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Insights</h1>
          <p className="text-gray-400 mt-2">AI analysis of responses with themes, sentiment, and recommendations</p>
        </div>
        <InsightsDashboard />
      </div>
    </AppLayout>
  )
}

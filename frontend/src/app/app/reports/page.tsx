import { AppLayout } from '@/components/layout/AppLayout'
import AnalyticsDashboard from '@/components/features/AnalyticsDashboard'

export default function ReportsPage() {
  return (
    <AppLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Reports & Analytics</h1>
          <p className="text-gray-400 mt-2">Monitor response metrics, trends, and generate executive summaries</p>
        </div>
        <AnalyticsDashboard />
      </div>
    </AppLayout>
  )
}

import { AppLayout } from '@/components/layout/AppLayout'
import { Card } from '@/components/ui/Card'

export default function InsightsPage() {
  return (
    <AppLayout>
      <Card className="p-6">
        <h2 className="font-display text-2xl font-bold">Insights</h2>
        <p className="text-text-muted mt-2">Theme clustering, sentiment trends, and AI summaries.</p>
      </Card>
    </AppLayout>
  )
}

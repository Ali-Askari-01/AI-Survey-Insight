import { AppLayout } from '@/components/layout/AppLayout'
import { Card } from '@/components/ui/Card'

export default function SurveysPage() {
  return (
    <AppLayout>
      <Card className="p-6">
        <h2 className="font-display text-2xl font-bold">My Surveys</h2>
        <p className="text-text-muted mt-2">Manage, publish, and review all survey activity.</p>
      </Card>
    </AppLayout>
  )
}

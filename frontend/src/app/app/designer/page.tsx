import { AppLayout } from '@/components/layout/AppLayout'
import { Card } from '@/components/ui/Card'

export default function DesignerPage() {
  return (
    <AppLayout>
      <Card className="p-6">
        <h2 className="font-display text-2xl font-bold">Survey Designer</h2>
        <p className="text-text-muted mt-2">Port of the existing AI-assisted survey design workflow.</p>
      </Card>
    </AppLayout>
  )
}

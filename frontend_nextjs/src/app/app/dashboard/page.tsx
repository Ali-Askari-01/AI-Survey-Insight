import { AppLayout } from '@/components/layout/AppLayout'
import { Card } from '@/components/ui/Card'

export default function DashboardPage() {
  return (
    <AppLayout>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card className="p-5"><h3 className="font-semibold">Active Surveys</h3><p className="text-3xl mt-2">12</p></Card>
        <Card className="p-5"><h3 className="font-semibold">Total Responses</h3><p className="text-3xl mt-2">1,284</p></Card>
        <Card className="p-5"><h3 className="font-semibold">Insights</h3><p className="text-3xl mt-2">87</p></Card>
      </div>
    </AppLayout>
  )
}

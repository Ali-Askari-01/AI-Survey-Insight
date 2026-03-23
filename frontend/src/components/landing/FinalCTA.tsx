import Link from 'next/link'
import { Button } from '@/components/ui/Button'

export function FinalCTA() {
  return (
    <section className="px-4 md:px-6 lg:px-8 py-16">
      <div className="max-w-4xl mx-auto bg-card border border-white/[0.07] rounded-3xl p-8 md:p-12 text-center shadow-card">
        <h2 className="font-display text-3xl md:text-5xl font-bold">Ready to Understand Your Users?</h2>
        <p className="text-text-muted mt-3">
          Start your first AI-powered research in under 2 minutes. No credit card required.
        </p>
        <div className="mt-6">
          <Link href="/app">
            <Button size="lg">Launch InsightAI Now</Button>
          </Link>
        </div>
      </div>
    </section>
  )
}

import Link from 'next/link'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'

export function HeroSection() {
  return (
    <section className="relative px-4 md:px-6 lg:px-8 pt-20 pb-14 md:pt-28 md:pb-20 overflow-hidden">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-20 left-0 w-72 h-72 rounded-full blur-3xl bg-accent-purple/20 animate-pulse-glow" />
        <div className="absolute top-10 right-0 w-64 h-64 rounded-full blur-3xl bg-accent-cyan/15 animate-pulse-glow" />
      </div>

      <div className="relative max-w-5xl mx-auto text-center">
        <Badge variant="cyan" className="mb-5">✦ Powered by Google Gemini AI</Badge>
        <h1 className="font-display text-4xl md:text-6xl font-black leading-[1.12] tracking-tight">
          Turn Conversations Into <span className="bg-gradient-accent bg-clip-text text-transparent">Clarity</span>
        </h1>
        <p className="mt-4 text-text-muted max-w-2xl mx-auto text-sm md:text-lg leading-relaxed">
          The AI research engine that designs your surveys, conducts adaptive interviews, and delivers insights all through natural conversation.
        </p>

        <div className="mt-8 flex flex-col md:flex-row gap-3 justify-center">
          <Link href="/app">
            <Button size="lg" className="w-full md:w-auto">Start for Free</Button>
          </Link>
          <a href="#how-it-works" className="w-full md:w-auto">
            <Button variant="secondary" size="lg" className="w-full">See How It Works</Button>
          </a>
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-center gap-2 text-xs text-text-muted">
          <Badge>No credit card</Badge>
          <Badge>2-min setup</Badge>
          <Badge>AI-powered</Badge>
        </div>
      </div>
    </section>
  )
}

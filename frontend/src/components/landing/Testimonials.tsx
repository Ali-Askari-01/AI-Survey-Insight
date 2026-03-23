'use client'

import { useMemo, useState } from 'react'
import { cn } from '@/lib/utils'

const testimonials = [
  {
    quote:
      'InsightAI cut our research cycle from 2 weeks to 2 days. The adaptive chat interviews get 3x richer responses than our old static surveys.',
    author: 'Sarah Kim',
    role: 'Head of Product, TechFlow',
  },
  {
    quote:
      'The AI-generated executive reports are genuinely impressive. I can share insights with stakeholders without spending hours on PowerPoints.',
    author: 'Marcus Rivera',
    role: 'UX Research Lead, DesignHub',
  },
  {
    quote:
      'The voice input and automatic transcription is a game-changer for accessibility. Our respondents love that they can just talk naturally.',
    author: 'Aisha Lemma',
    role: 'Founder, UserFirst',
  },
]

export function Testimonials() {
  const [active, setActive] = useState(0)
  const dots = useMemo(() => testimonials.map((_, i) => i), [])

  return (
    <section id="testimonials" className="px-4 md:px-6 lg:px-8 py-14 overflow-hidden">
      <div className="max-w-6xl mx-auto">
        <div className="text-center max-w-2xl mx-auto mb-8">
          <h2 className="font-display font-bold text-3xl md:text-4xl">Loved by product teams</h2>
          <p className="text-text-muted mt-3">See what researchers and product leaders are saying.</p>
        </div>

        <div
          className="flex md:grid md:grid-cols-3 gap-4 overflow-x-auto md:overflow-visible snap-x snap-mandatory pb-3"
          onScroll={(e) => {
            const el = e.currentTarget
            if (window.innerWidth >= 768) return
            const idx = Math.round(el.scrollLeft / Math.max(el.clientWidth, 1))
            setActive(Math.max(0, Math.min(testimonials.length - 1, idx)))
          }}
        >
          {testimonials.map((t) => (
            <article
              key={t.author}
              className="min-w-[82vw] md:min-w-0 max-w-[320px] md:max-w-none snap-start border border-white/[0.07] rounded-2xl p-6 bg-card"
            >
              <p className="text-sm leading-relaxed">“{t.quote}”</p>
              <div className="mt-4">
                <p className="font-semibold">{t.author}</p>
                <p className="text-xs text-text-muted">{t.role}</p>
              </div>
            </article>
          ))}
        </div>

        <div className="flex md:hidden justify-center gap-2 mt-4">
          {dots.map((d) => (
            <button
              key={d}
              className={cn('h-1.5 rounded-full transition-all', active === d ? 'w-4 bg-accent-cyan' : 'w-1.5 bg-text-subtle')}
              aria-label={`Go to testimonial ${d + 1}`}
            />
          ))}
        </div>
      </div>
    </section>
  )
}

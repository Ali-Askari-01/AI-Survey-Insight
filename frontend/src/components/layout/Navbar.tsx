'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/Button'
import { Menu, X } from 'lucide-react'

const links = [
  { label: 'Features', href: '#features' },
  { label: 'How It Works', href: '#how-it-works' },
  { label: 'Testimonials', href: '#testimonials' },
]

export function Navbar() {
  const [open, setOpen] = useState(false)

  return (
    <header
      className="sticky top-0 z-50 backdrop-blur-xl border-b border-white/[0.06]"
      style={{ background: 'rgba(3,7,18,0.92)' }}
    >
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        <Link href="/" className="font-display font-black text-xl bg-gradient-accent bg-clip-text text-transparent">
          InsightAI
        </Link>

        <ul className="hidden md:flex items-center gap-8">
          {links.map((l) => (
            <li key={l.href}>
              <a href={l.href} className="text-text-muted hover:text-text-primary transition-colors text-sm font-medium">
                {l.label}
              </a>
            </li>
          ))}
        </ul>

        <Link href="/app" className="hidden md:inline-flex">
          <Button size="sm">Start Free</Button>
        </Link>

        <button
          onClick={() => setOpen((o) => !o)}
          className="md:hidden flex items-center justify-center w-11 h-11 rounded-xl text-text-muted hover:text-text-primary hover:bg-white/5 transition-all"
          aria-label="Toggle menu"
          aria-expanded={open}
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </nav>

      {open && (
        <div className="md:hidden border-t border-white/[0.06] bg-surface">
          <ul className="flex flex-col">
            {links.map((l) => (
              <li key={l.href}>
                <a
                  href={l.href}
                  onClick={() => setOpen(false)}
                  className="flex items-center px-6 py-4 text-base text-text-muted hover:text-text-primary hover:bg-white/5 transition-all border-b border-white/[0.04] min-h-[52px]"
                >
                  {l.label}
                </a>
              </li>
            ))}
            <li className="p-4">
              <Link href="/app" onClick={() => setOpen(false)}>
                <Button size="lg" className="w-full">
                  Start Free
                </Button>
              </Link>
            </li>
          </ul>
        </div>
      )}
    </header>
  )
}

'use client'

import { usePathname } from 'next/navigation'
import Link from 'next/link'
import { cn } from '@/lib/utils'
import { LayoutDashboard, PenSquare, ClipboardList, Lightbulb, FileBarChart } from 'lucide-react'

const tabs = [
  { label: 'Dashboard', href: '/app/dashboard', icon: LayoutDashboard },
  { label: 'Designer', href: '/app/designer', icon: PenSquare },
  { label: 'Surveys', href: '/app/surveys', icon: ClipboardList },
  { label: 'Insights', href: '/app/insights', icon: Lightbulb },
  { label: 'Reports', href: '/app/reports', icon: FileBarChart },
]

export function AppLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname()

  return (
    <div className="min-h-screen bg-bg flex">
      <aside className="hidden md:flex flex-col w-60 fixed top-0 left-0 h-screen bg-surface border-r border-white/[0.07] z-40">
        <div className="h-16 flex items-center px-6 border-b border-white/[0.07]">
          <span className="font-display font-black text-lg bg-gradient-accent bg-clip-text text-transparent">InsightAI</span>
        </div>
        <nav className="flex-1 py-4 overflow-y-auto">
          {tabs.map((tab) => {
            const active = path.startsWith(tab.href)
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={cn(
                  'flex items-center gap-3 px-6 py-3.5 text-sm font-medium transition-all',
                  'hover:bg-white/5 hover:text-text-primary border-l-2',
                  active ? 'border-accent-cyan text-accent-cyan bg-accent-cyan/5' : 'border-transparent text-text-muted'
                )}
              >
                <tab.icon size={18} />
                {tab.label}
              </Link>
            )
          })}
        </nav>
        <div className="p-4 border-t border-white/[0.07]">
          <p className="text-xs text-text-subtle font-mono">AI Insight Engine v1.0</p>
        </div>
      </aside>

      <main className={cn('flex-1 min-h-screen', 'md:ml-60', 'pb-[calc(70px+env(safe-area-inset-bottom))] md:pb-0')}>
        <header className="md:hidden sticky top-0 z-30 h-14 flex items-center justify-between px-4 bg-surface/90 backdrop-blur-xl border-b border-white/[0.07]">
          <span className="font-display font-bold text-base bg-gradient-accent bg-clip-text text-transparent">InsightAI</span>
          <select className="text-xs bg-card border border-white/10 rounded-lg px-2 py-1.5 text-text-muted outline-none">
            <option>Executive</option>
            <option>Product Manager</option>
            <option>Designer</option>
            <option>Engineer</option>
          </select>
        </header>

        <div className="p-4 md:p-8">{children}</div>
      </main>

      <nav
        className="md:hidden fixed bottom-0 left-0 right-0 z-50 flex items-stretch bg-surface/95 backdrop-blur-xl border-t border-white/[0.08]"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        {tabs.map((tab) => {
          const active = path.startsWith(tab.href)
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                'flex-1 flex flex-col items-center justify-center gap-1',
                'min-h-[56px] py-2 px-1 relative',
                'transition-all active:scale-90 select-none',
                active ? 'text-accent-cyan' : 'text-text-subtle'
              )}
            >
              {active && (
                <span className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-accent-cyan rounded-full shadow-glow-cyan" />
              )}
              <tab.icon size={20} strokeWidth={active ? 2.5 : 1.8} />
              <span className="text-[10px] font-medium tracking-wide">{tab.label}</span>
            </Link>
          )
        })}
      </nav>

      <MicFAB />
    </div>
  )
}

function MicFAB() {
  return (
    <button
      className="md:hidden fixed z-40 right-5 w-14 h-14 rounded-full bg-linear-to-br from-accent-cyan to-accent-purple flex items-center justify-center text-2xl shadow-glow-cyan active:scale-90 transition-transform"
      style={{ bottom: 'calc(72px + env(safe-area-inset-bottom))' }}
      aria-label="Voice input"
      onClick={() => {
        document.querySelector('[data-voice-trigger]')?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      }}
    >
      🎙️
    </button>
  )
}

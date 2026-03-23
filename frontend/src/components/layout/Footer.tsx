import Link from 'next/link'

export function Footer() {
  return (
    <footer className="border-t border-white/[0.07] py-8 px-4 md:px-6">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3 text-sm text-text-muted">
        <p>© 2026 InsightAI. Built with Google Gemini AI.</p>
        <Link href="/app" className="text-accent-cyan hover:opacity-80 transition-opacity">
          Go to App
        </Link>
      </div>
    </footer>
  )
}

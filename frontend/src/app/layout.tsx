import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'InsightAI — AI-Powered Survey & Insight Engine',
  description: 'Turn conversations into clarity with AI-powered surveys',
  viewport: {
    width: 'device-width',
    initialScale: 1,
    viewportFit: 'cover',
  },
  themeColor: '#030712',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}

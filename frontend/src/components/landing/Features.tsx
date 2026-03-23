import { Card } from '@/components/ui/Card'

const features = [
  {
    title: 'AI Survey Designer',
    text: 'Describe your research goal in plain English. Our AI generates perfectly aligned interview questions with smart follow-ups.',
  },
  {
    title: 'Adaptive Chat Interviews',
    text: 'WhatsApp-style AI interviews that dynamically adapt to each respondent. Every conversation is unique and deeply insightful.',
  },
  {
    title: 'Voice Input',
    text: 'Let respondents speak naturally. AI transcription converts voice to text with sentiment analysis and automatic processing.',
  },
  {
    title: 'Real-Time Analytics',
    text: 'Watch sentiment trends, theme clusters, and insights emerge in real-time as responses flow in. No waiting.',
  },
  {
    title: 'Semantic Memory',
    text: 'The AI remembers context across the entire interview, building a knowledge graph to ask progressively smarter questions.',
  },
  {
    title: 'Executive Reports',
    text: 'AI-generated executive summaries, sentiment breakdowns, and actionable recommendations ready for stakeholders.',
  },
]

export function Features() {
  return (
    <section id="features" className="px-4 md:px-6 lg:px-8 py-14">
      <div className="max-w-6xl mx-auto">
        <div className="text-center max-w-3xl mx-auto mb-8">
          <h2 className="font-display font-bold text-3xl md:text-4xl">Everything to understand your users</h2>
          <p className="text-text-muted mt-3">
            From survey creation to executive reports, AI handles the heavy lifting so you can focus on building better products.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {features.map((f) => (
            <Card key={f.title} glow className="p-5">
              <h3 className="font-semibold text-lg">{f.title}</h3>
              <p className="text-text-muted text-sm mt-2 leading-relaxed">{f.text}</p>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}

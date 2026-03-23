const steps = [
  {
    title: 'Describe Your Goal',
    text: 'Tell the AI what you want to learn. It asks follow-up questions to understand your research needs.',
  },
  {
    title: 'AI Generates Survey',
    text: 'Targeted questions with follow-ups are created, aligned precisely to your research goal.',
  },
  {
    title: 'Collect Responses',
    text: 'Deploy via web form, AI chat, or voice input. The AI adapts in real-time to each respondent.',
  },
  {
    title: 'Get Insights',
    text: 'Receive auto-generated reports with sentiment analysis, theme clustering, and actionable recommendations.',
  },
]

export function HowItWorks() {
  return (
    <section id="how-it-works" className="px-4 md:px-6 lg:px-8 py-14">
      <div className="max-w-6xl mx-auto">
        <div className="text-center max-w-2xl mx-auto mb-8">
          <h2 className="font-display font-bold text-3xl md:text-4xl">From idea to insight in 4 steps</h2>
          <p className="text-text-muted mt-3">No survey design expertise needed. Just describe what you want to learn.</p>
        </div>

        <div className="flex flex-col md:flex-row gap-4 border-l-2 md:border-l-0 md:border-t-0 border-accent-cyan/40 pl-4 md:pl-0">
          {steps.map((s, i) => (
            <div key={s.title} className="flex-1 border border-white/[0.07] rounded-2xl p-5 bg-card/70 relative">
              <div className="text-3xl font-black bg-gradient-accent bg-clip-text text-transparent">{i + 1}</div>
              <h3 className="mt-2 font-semibold">{s.title}</h3>
              <p className="text-text-muted text-sm mt-2 leading-relaxed">{s.text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

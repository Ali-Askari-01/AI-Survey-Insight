export function StatsBar() {
  const stats = [
    { value: '10,000+', label: 'Surveys Created' },
    { value: '3x', label: 'Richer Responses' },
    { value: '< 2 min', label: 'Setup Time' },
    { value: 'Real-time', label: 'Analysis' },
  ]

  return (
    <section className="px-4 md:px-6 lg:px-8 py-4">
      <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-3">
        {stats.map((stat) => (
          <div key={stat.label} className="bg-card border border-white/[0.07] rounded-xl p-4 text-center">
            <div className="text-2xl font-black bg-gradient-accent bg-clip-text text-transparent">{stat.value}</div>
            <div className="text-[11px] uppercase tracking-wide text-text-muted mt-1">{stat.label}</div>
          </div>
        ))}
      </div>
    </section>
  )
}

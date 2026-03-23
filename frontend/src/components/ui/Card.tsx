import { cn } from '@/lib/utils'

export function Card({
  className,
  children,
  glow = false,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { glow?: boolean }) {
  return (
    <div
      className={cn(
        'bg-card border border-white/[0.07] rounded-2xl relative overflow-hidden',
        'transition-all duration-300',
        glow && 'shadow-glow-cyan hover:border-accent-cyan/20',
        className
      )}
      {...props}
    >
      {glow && (
        <div className="absolute inset-0 bg-linear-to-br from-accent-cyan/[0.03] to-transparent pointer-events-none" />
      )}
      {children}
    </div>
  )
}

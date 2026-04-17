import { cn } from '@/lib/utils'

type BadgeVariant = 'cyan' | 'purple' | 'green' | 'gold' | 'muted'

export function Badge({
  variant = 'muted',
  className,
  children,
}: {
  variant?: BadgeVariant
  className?: string
  children: React.ReactNode
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full border',
        {
          'bg-accent-cyan/10 border-accent-cyan/20 text-accent-cyan': variant === 'cyan',
          'bg-accent-purple/10 border-accent-purple/20 text-accent-purple': variant === 'purple',
          'bg-accent-green/10 border-accent-green/20 text-accent-green': variant === 'green',
          'bg-amber-500/10 border-amber-500/20 text-amber-400': variant === 'gold',
          'bg-white/[0.04] border-white/10 text-text-muted': variant === 'muted',
        },
        className
      )}
    >
      {children}
    </span>
  )
}

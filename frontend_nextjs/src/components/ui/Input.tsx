import { cn } from '@/lib/utils'
import { forwardRef, type InputHTMLAttributes } from 'react'

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement> & { label?: string; hint?: string; error?: string }
>(({ className, label, hint, error, ...props }, ref) => (
  <div className="flex flex-col gap-1.5 w-full">
    {label && <label className="text-sm font-medium text-text-muted">{label}</label>}
    <input
      ref={ref}
      className={cn(
        'w-full bg-white/[0.04] border border-white/10 rounded-xl px-4 py-3',
        'text-text-primary placeholder:text-text-subtle',
        'text-[16px]',
        'outline-none transition-all duration-200',
        'focus:border-accent-cyan/40 focus:bg-accent-cyan/[0.03] focus:ring-2 focus:ring-accent-cyan/10',
        error && 'border-red-500/40 focus:border-red-500/60',
        className
      )}
      {...props}
    />
    {hint && !error && <p className="text-xs text-text-subtle">{hint}</p>}
    {error && <p className="text-xs text-red-400">{error}</p>}
  </div>
))
Input.displayName = 'Input'

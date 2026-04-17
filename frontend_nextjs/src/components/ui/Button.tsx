'use client'

import { cn } from '@/lib/utils'
import { type ButtonHTMLAttributes, forwardRef } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', loading, children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          'inline-flex items-center justify-center font-semibold rounded-xl transition-all duration-200',
          'min-h-[44px] min-w-[44px] active:scale-95',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-cyan',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          {
            'bg-linear-to-r from-accent-cyan to-accent-purple text-black shadow-glow-cyan hover:opacity-90 hover:-translate-y-0.5':
              variant === 'primary',
            'bg-card border border-white/10 text-text-primary hover:border-accent-cyan/40':
              variant === 'secondary',
            'bg-transparent text-text-muted hover:text-text-primary hover:bg-white/5':
              variant === 'ghost',
            'bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20':
              variant === 'danger',
          },
          {
            'text-sm px-4 py-2': size === 'sm',
            'text-base px-6 py-3': size === 'md',
            'text-lg px-8 py-4': size === 'lg',
          },
          className
        )}
        {...props}
      >
        {loading ? (
          <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-2" />
        ) : null}
        {children}
      </button>
    )
  }
)
Button.displayName = 'Button'

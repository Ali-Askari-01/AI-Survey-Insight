import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        bg: '#030712',
        surface: '#0d1117',
        card: '#111827',
        border: 'rgba(255,255,255,0.07)',
        accent: {
          cyan: '#00e5ff',
          purple: '#7c3aed',
          green: '#10b981',
          gold: '#f59e0b',
        },
        text: {
          primary: '#f1f5f9',
          muted: '#64748b',
          subtle: '#334155',
        },
      },
      fontFamily: {
        display: ['Playfair Display', 'Georgia', 'serif'],
        mono: ['Space Mono', 'monospace'],
        sans: ['DM Sans', 'sans-serif'],
      },
      backgroundImage: {
        'gradient-accent': 'linear-gradient(135deg, #00e5ff, #7c3aed)',
        'gradient-hero': 'linear-gradient(135deg, #030712 0%, #0d0f1a 100%)',
      },
      animation: {
        'fade-up': 'fadeUp 0.7s ease forwards',
        'fade-in': 'fadeIn 0.6s ease forwards',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        float: 'float 8s linear infinite',
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'none' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        pulseGlow: {
          '0%,100%': { opacity: '0.3' },
          '50%': { opacity: '0.6' },
        },
        float: {
          '0%': { transform: 'translateY(100vh)', opacity: '0' },
          '10%': { opacity: '0.6' },
          '90%': { opacity: '0.3' },
          '100%': { transform: 'translateY(-100px)', opacity: '0' },
        },
      },
      boxShadow: {
        'glow-cyan': '0 0 40px rgba(0,229,255,0.15)',
        'glow-purple': '0 0 40px rgba(124,58,237,0.15)',
        card: '0 4px 24px rgba(0,0,0,0.4)',
      },
    },
  },
  plugins: [],
}

export default config

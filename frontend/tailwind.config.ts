import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#0d0d0d',
        'bg-surface': '#161616',
        'bg-elevated': '#1f1f1f',
        'border-default': '#2a2a2a',
        'accent': '#7c3aed',
        'accent-hover': '#6d28d9',
        'text-primary': '#e8e8e8',
        'text-secondary': '#888888',
        'text-muted': '#555555',
        'success': '#10b981',
        'error': '#ef4444',
        'warning': '#f59e0b',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'blink': 'blink 1s step-end infinite',
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
      },
    },
  },
  plugins: [],
}

export default config

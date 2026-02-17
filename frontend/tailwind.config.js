/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        forexia: {
          bg: '#0a0e17',
          dark: '#0a0e17',
          panel: '#111827',
          border: '#1e293b',
          accent: '#3b82f6',
          gold: '#f59e0b',
          green: '#10b981',
          red: '#ef4444',
          purple: '#8b5cf6',
          cyan: '#06b6d4',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};

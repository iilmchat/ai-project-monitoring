/** Tailwind CSS configuration — IIRuChating brand book (v1.1, M3 Fidelity). */
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          black: '#000000',
          white: '#FFFFFF',
          violet: '#8B5CF6',
          blue: '#0EA5E9',
          emerald: '#10B981',
          dark: '#1E293B',
        },
        primary: {
          DEFAULT: '#6B38D4',
          container: '#8455EF',
          fixed: '#E9DDFF',
        },
        tertiary: '#006591',
        surface: {
          DEFAULT: '#FEF7FF',
          container: '#F3EBF8',
          high: '#EDE5F3',
        },
        'on-surface': '#1D1A23',
        'on-surface-variant': '#494454',
        outline: '#7B7486',
        'outline-variant': '#CBC3D7',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        display: ['Manrope', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

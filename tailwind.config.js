/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './templates/**/*.html',
    './**/templates/**/*.html',
    './static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        // Design system Holystyl — turquoise #2ABFBF (oklch 72% 0.13 192)
        brand: {
          DEFAULT: '#2abfbf',
          50: '#e9fbfb',
          100: '#c9f4f4',
          400: '#3fd0d0',
          500: '#2abfbf',
          600: '#1f9d9d',
          700: '#1a7e7e',
        },
        // Palette charts (turquoise, vert vibrant, ambre, rouge, violet)
        chart: {
          1: '#2abfbf',
          2: '#22c55e',
          3: '#f5a623',
          4: '#ef4444',
          5: '#a855f7',
        },
      },
      fontFamily: {
        sans: ['Lexend', 'Lexend Deca', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'glow-teal': '0 0 20px rgba(42,191,191,0.4), 0 0 60px rgba(42,191,191,0.15)',
        'glow-green': '0 0 20px rgba(34,197,94,0.35), 0 0 60px rgba(34,197,94,0.12)',
      },
    },
  },
  plugins: [],
};

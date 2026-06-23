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
        // Identité « eau » — bleu profond → aqua
        brand: {
          DEFAULT: '#0e7490',
          50: '#ecfeff',
          100: '#cff7fb',
          200: '#a5eef5',
          300: '#67dded',
          400: '#22d3ee', // aqua vif (accent / gouttes)
          500: '#0891b2',
          600: '#0e7490', // primaire (boutons/texte sur fond clair)
          700: '#155e75',
          800: '#164e63',
          900: '#0b3b49',
        },
        // Vert végétal — réservé aux états « bon / efficient »
        crop: {
          DEFAULT: '#65a30d',
          500: '#65a30d',
          600: '#4d7c0f',
        },
        // Neutres chauds (agricole, doux au soleil)
        sand: {
          50: '#fafaf7',
          100: '#f4f2ec',
          200: '#e7e5dd',
          300: '#d6d3c8',
          700: '#5b6b72',
          900: '#1a2b33',
        },
      },
      fontFamily: {
        sans: ['"Atkinson Hyperlegible"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};

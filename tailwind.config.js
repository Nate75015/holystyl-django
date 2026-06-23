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
        // Couleur de marque Holystyl (teal / vert vibrant)
        brand: {
          DEFAULT: '#06b6c4',
          50: '#ecfeff',
          500: '#06b6c4',
          600: '#0891a4',
          700: '#0e7490',
        },
      },
      fontFamily: {
        sans: ['Lexend', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};

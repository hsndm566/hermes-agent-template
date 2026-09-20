/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        ar: ['"IBM Plex Sans Arabic"', '"Tajawal"', 'sans-serif'],
        en: ['"Inter"', 'sans-serif'],
      },
      colors: {
        canvas: '#F7F5F0',
        surface: '#FFFFFF',
        ink: {
          900: '#1B1E1C',
          700: '#33372F',
          500: '#5C6259',
          300: '#9BA096',
          200: '#D9DBD3',
          100: '#EDEEE8',
        },
        moss: {
          900: '#173129',
          700: '#1F4A3C',
          600: '#28604D',
          500: '#2F7A5F',
          400: '#4C9679',
          200: '#BFE0D0',
          100: '#E4F1EA',
          50: '#F2F8F4',
        },
        amber: {
          600: '#B4791E',
          500: '#CC8F2E',
          100: '#FBEED9',
        },
        rose: {
          600: '#B23A3A',
          100: '#FBE7E7',
        },
      },
      boxShadow: {
        card: '0 1px 2px rgba(27,30,28,0.04), 0 4px 16px rgba(27,30,28,0.05)',
        pop: '0 8px 30px rgba(23,49,41,0.14)',
      },
      borderRadius: {
        xl2: '1.1rem',
      },
    },
  },
  plugins: [],
}

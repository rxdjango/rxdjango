/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          100: '#F5F8F8',
          200: '#E1EBEA',
          300: '#C3D6D4',
          400: '#9BBBB8',
          500: '#377771',
          600: '#2F6560',
          700: '#27534F',
          800: '#1E413E',
          900: '#16302D',
          DEFAULT: '#377771',
        },
        surface: '#F5F5F0',
        ink: '#100B00',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};

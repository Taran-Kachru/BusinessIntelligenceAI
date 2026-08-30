/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Wealth palette — #103438 / #566677 / #B0BFD1
        w: {
          dark:   '#103438',
          mid:    '#566677',
          silver: '#B0BFD1',
        },
      },
    },
  },
  plugins: [],
}

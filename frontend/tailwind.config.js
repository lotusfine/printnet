/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sketch: ["'Cabin Sketch'", 'cursive'],
        chalk: ["'Fredericka the Great'", 'serif'],
        paint: ["'Finger Paint'", 'cursive'],
      },
    },
  },
  plugins: [],
}
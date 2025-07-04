/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./static/**/*.{html,js}"], // Add paths to all of your template files
  theme: {
    extend: {
      fontFamily: {
        'vazir': ['Vazirmatn', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

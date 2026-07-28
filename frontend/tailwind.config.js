/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1a1a2e",
        accent: "#4f46e5",
      },
    },
  },
  plugins: [],
};

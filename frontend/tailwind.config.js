/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        mono: ["'JetBrains Mono'", "monospace"],
        display: ["'Space Grotesk'", "sans-serif"],
      },
      colors: {
        surface: {
          0: "#080b0f",
          1: "#0d1117",
          2: "#161b22",
          3: "#21262d",
          4: "#30363d",
        },
        accent: {
          cyan:   "#38bdf8",
          green:  "#22c55e",
          red:    "#ef4444",
          orange: "#f0883e",
          purple: "#a78bfa",
          yellow: "#fbbf24",
        },
      },
    },
  },
  plugins: [],
};

import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "liaison-surface": "var(--liaison-surface)",
        "liaison-surface-low": "var(--liaison-surface-low)",
        "liaison-surface-container": "var(--liaison-surface-container)",
        "liaison-surface-high": "var(--liaison-surface-high)",
        "liaison-primary": "var(--liaison-primary)",
        "liaison-primary-container": "var(--liaison-primary-container)",
        "liaison-teal": "var(--liaison-teal)",
        "liaison-gold": "var(--liaison-gold)",
        "liaison-on-surface": "var(--liaison-on-surface)",
        "liaison-on-surface-variant": "var(--liaison-on-surface-variant)",
        "liaison-outline-variant": "var(--liaison-outline-variant)",
        "liaison-error": "var(--liaison-error)",
        "liaison-warn": "var(--liaison-warn)",
      },
      fontFamily: {
        body: ["var(--font-body)", "system-ui", "sans-serif"],
        headline: ["var(--font-headline)", "Georgia", "serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;

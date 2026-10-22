import type { Config } from "tailwindcss";
const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#090a0d",
        "bg-soft": "#0f1115",
        card: "#111419",
        line: "#1e242d",
        "line-bright": "#2a313d",
        fg: "#f0f2f5",
        "fg-dim": "#a0a8b3",
        "fg-faint": "#6b7480",
        accent: "#f5a524",
        "accent-dim": "#c4821a",
        good: "#4ec9a0",
        danger: "#f0645c",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
      boxShadow: {
        glow: "0 12px 48px -8px rgba(0,0,0,0.5)",
      },
    },
  },
  plugins: [],
};
export default config;

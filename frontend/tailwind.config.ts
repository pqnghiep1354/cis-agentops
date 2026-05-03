import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        gold:      "#DB9628",
        "gold-light": "#E8B455",
        "gold-dark":  "#B87B1A",
        ink:       "#1F2933",
        "ink-light":  "#2D3748",
        slate:     "#33363D",
        mist:      "#F8F6F2",
        "mist-dark":  "#EDE9E3",
        success:   "#22c55e",
        error:     "#ef4444",
        warning:   "#f59e0b",
      },
      fontFamily: {
        display: ["var(--font-playfair)", "Georgia", "serif"],
        body:    ["var(--font-dm-sans)", "system-ui", "sans-serif"],
        mono:    ["var(--font-jetbrains)", "monospace"],
      },
      backgroundImage: {
        "ink-gradient":  "linear-gradient(135deg, #1F2933 0%, #2D3748 100%)",
        "gold-gradient": "linear-gradient(135deg, #DB9628 0%, #E8B455 100%)",
        "subtle-grid":   "radial-gradient(circle, #33363D 1px, transparent 1px)",
      },
      animation: {
        "pulse-gold": "pulse-gold 2s ease-in-out infinite",
        "slide-up":   "slide-up 0.5s ease-out forwards",
        "fade-in":    "fade-in 0.4s ease-out forwards",
        shimmer:      "shimmer 1.5s infinite",
      },
      keyframes: {
        "pulse-gold": {
          "0%,100%": { boxShadow: "0 0 0 0 rgba(219,150,40,0.3)" },
          "50%":      { boxShadow: "0 0 0 8px rgba(219,150,40,0)" },
        },
        "slide-up": {
          "0%":   { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%":   { opacity: "0" },
          "100%": { opacity: "1" },
        },
        shimmer: {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
    },
  },
  plugins: [],
};
export default config;

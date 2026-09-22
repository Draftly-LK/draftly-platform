import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "var(--canvas)",
        surface: "var(--surface)",
        ink: "var(--ink)",
        "muted-ink": "var(--muted-ink)",
        border: "var(--border)",
        "border-strong": "var(--border-strong)",
        forest: "var(--forest)",
        "soft-green": "var(--soft-green)",
        teal: "var(--teal)",
        amber: "var(--amber)",
        "amber-text": "var(--amber-text)",
        red: "var(--red)",
        "selected-bg": "var(--selected-bg)",
        "hover-bg": "var(--hover-bg)",
        "active-bg": "var(--active-bg)",
        "disabled-fg": "var(--disabled-fg)",
        "disabled-bg": "var(--disabled-bg)",
        "amber-bg": "var(--amber-bg)",
        "teal-bg": "var(--teal-bg)",
        "red-bg": "var(--red-bg)",
        "on-dark": "var(--on-dark)",
        "on-dark-muted": "var(--on-dark-muted)",
        "panel-dark": "var(--panel-dark)",
        "border-on-dark": "var(--border-on-dark)",
        scrim: "var(--scrim)"
      },
      fontFamily: {
        ui: ["var(--font-plex)", "var(--font-noto-sans-si)", "sans-serif"],
        heading: ["var(--font-newsreader)", "var(--font-noto-serif-si)", "serif"]
      },
      outlineColor: {
        ring: "var(--ring)"
      },
      borderRadius: { DEFAULT: "6px", dialog: "8px" },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } }
      },
      animation: { "fade-in": "fade-in 250ms ease-out both" },
      boxShadow: {
        popover: "var(--shadow-popover)",
        dialog: "var(--shadow-dialog)",
        toast: "var(--shadow-toast)"
      }
    }
  },
  plugins: []
} satisfies Config;


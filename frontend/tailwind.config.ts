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
        scrim: "var(--scrim)",
        "navy-950": "var(--navy-950)",
        "navy-900": "var(--navy-900)",
        "navy-800": "var(--navy-800)",
        gold: "var(--gold)",
        "gold-strong": "var(--gold-strong)",
        "gold-soft": "var(--gold-soft)"
      },
      fontFamily: {
        ui: ["var(--font-plex)", "var(--font-noto-sans-si)", "sans-serif"],
        heading: ["var(--font-plex)", "var(--font-noto-sans-si)", "sans-serif"],
        display: ["var(--font-serif)", "var(--font-noto-serif-si)", "Georgia", "serif"]
      },
      outlineColor: {
        ring: "var(--ring)"
      },
      borderRadius: { DEFAULT: "6px", dialog: "8px", card: "10px" },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "rise-in": { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "none" } }
      },
      animation: {
        "fade-in": "fade-in 250ms ease-out both",
        "rise-in": "rise-in 320ms cubic-bezier(0.2, 0.7, 0.2, 1) both"
      },
      boxShadow: {
        popover: "var(--shadow-popover)",
        dialog: "var(--shadow-dialog)",
        toast: "var(--shadow-toast)",
        card: "var(--shadow-card)",
        raised: "var(--shadow-raised)"
      }
    }
  },
  plugins: []
} satisfies Config;

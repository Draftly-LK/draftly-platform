import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    // The type scale is closed: 12, 13, 14, 16, 18, 20, 24, 30px. Anything
    // else (text-4xl, text-[17px]) fails to compile into a size on purpose.
    fontSize: {
      xs: ["12px", { lineHeight: "16px" }],
      compact: ["13px", { lineHeight: "20px" }],
      sm: ["14px", { lineHeight: "20px" }],
      base: ["16px", { lineHeight: "24px" }],
      lg: ["18px", { lineHeight: "26px" }],
      xl: ["20px", { lineHeight: "28px" }],
      "2xl": ["24px", { lineHeight: "32px" }],
      "3xl": ["30px", { lineHeight: "38px" }]
    },
    extend: {
      colors: {
        success: "var(--success)",
        "success-bg": "var(--success-bg)",
        "gold-hover": "var(--gold-hover)",
        "ring-on-dark": "var(--ring-on-dark)",
        canvas: "var(--canvas)",
        surface: "var(--surface)",
        ink: "var(--ink)",
        "muted-ink": "var(--muted-ink)",
        border: "var(--border)",
        "border-strong": "var(--border-strong)",
        "border-control": "var(--border-control)",
        "red-hover": "var(--red-hover)",
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
        ring: "var(--ring)",
        "ring-on-dark": "var(--ring-on-dark)"
      },
      borderRadius: { DEFAULT: "12px", dialog: "16px", card: "16px", control: "9999px" },
      keyframes: {
        // Page-change bar: fast at first, then creeping towards 90% until the page lands.
        "nav-progress": { from: { width: "0%" }, "20%": { width: "45%" }, to: { width: "90%" } }
      },
      animation: {
        "nav-progress": "nav-progress 8s cubic-bezier(0.1, 0.6, 0.2, 1) both"
      },
      boxShadow: {
        popover: "var(--shadow-popover)",
        dialog: "var(--shadow-dialog)",
        toast: "var(--shadow-toast)"
      }
    }
  },
  plugins: []
} satisfies Config;

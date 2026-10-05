# Support page spacing review

- Settings, Billing, Profile, and Help use the same centered 1240px maximum
  width and 24px padding as Matters and History.
- Settings and Profile start directly at the content padding.
- Help uses compact divided rows, 20px icons, and smaller headings.
- Billing plan columns adapt to available width, including the sidebar.
- Type checking, support component lint, and all three billing tests passed.
- Browser screenshots cover 1440, 768, 390, and 360px. Raw measurements are
  recorded in probes.json beside the screenshots.
- The current application serves English only; no locale behavior was changed.
- Visual acceptance remains available for human review in the local preview.

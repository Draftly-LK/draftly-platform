/**
 * A matter's sections, in the order the work runs: shared by the tab bar and the
 * previous/next bar so the two can never disagree.
 */
export const MATTER_SECTIONS = [
  "overview",
  "checklist",
  "documents",
  "facts",
  "checks",
  "drafts",
  "exports",
] as const;

export type MatterSection = (typeof MATTER_SECTIONS)[number];

const SECTION_PATH: Record<MatterSection, string> = {
  overview: "",
  checklist: "/checklist",
  documents: "/documents",
  facts: "/facts",
  checks: "/checks",
  drafts: "/drafts",
  exports: "/exports",
};

export function matterSectionHref(
  section: MatterSection,
  matterId: string,
): string {
  return `/matters/${matterId}${SECTION_PATH[section]}`;
}

/** The section a path belongs to; sub-pages (a document's review) count as their section. */
export function sectionForPath(
  pathname: string,
  matterId: string,
): MatterSection | null {
  if (pathname === `/matters/${matterId}/missing-documents`) return "documents";
  if (pathname.startsWith(`/matters/${matterId}/workflow`)) return "checks";
  for (const section of MATTER_SECTIONS) {
    const href = matterSectionHref(section, matterId);
    if (
      pathname === href ||
      (section !== "overview" && pathname.startsWith(`${href}/`))
    )
      return section;
  }
  return null;
}

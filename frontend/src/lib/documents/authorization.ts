import type {
  DocumentKind,
  DocumentRelation,
  MatterType,
  RegistrationRegime,
} from "@/types";

/** Authorized evidence kinds for a regime + transaction. M2: identity only on RTA transfer. */
// TODO(api): GET /api/regimes/{regime}/transactions/{type}/authorized-document-kinds
export function authorizedKinds(
  regime: RegistrationRegime,
  type: MatterType,
): DocumentKind[] {
  if (regime === "rta" && type === "transfer") return ["identity"];
  return [];
}

export function relationForKind(
  kind: DocumentKind,
  regime: RegistrationRegime,
  type: MatterType,
): DocumentRelation {
  const authorized = authorizedKinds(regime, type);
  if (authorized.length === 0) {
    return kind === "other" ? "unclassified" : "unrelated";
  }
  if (authorized.includes(kind)) return "authorized";
  if (kind === "other") return "unclassified";
  return "unrelated";
}

export function hasAuthorizedDocumentCatalog(
  regime: RegistrationRegime,
  type: MatterType,
): boolean {
  return authorizedKinds(regime, type).length > 0;
}

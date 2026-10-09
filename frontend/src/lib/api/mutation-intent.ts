/** Only opaque retry metadata is retained; the lawyer re-enters the request. */
const lifetime = 24 * 60 * 60 * 1000;
type Metadata = {
  version: 1;
  key: string;
  digest: string;
  createdAt: number;
  expectedVersion?: number;
};
export type ManualIntent = Metadata & {
  storageKey: string;
  persistent: boolean;
};
const memory = new Map<string, Metadata>();
function canonical(value: unknown): unknown {
  if (
    (typeof Blob !== "undefined" && value instanceof Blob) ||
    (typeof FormData !== "undefined" && value instanceof FormData)
  )
    throw new Error("Binary requests require explicit byte hashing");
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value)
        .filter(([, v]) => v !== undefined)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, v]) => [k, canonical(v)]),
    );
  return value;
}
function valid(value: unknown): value is Metadata {
  if (!value || typeof value !== "object") return false;
  const item = value as Metadata;
  return (
    item.version === 1 &&
    typeof item.key === "string" &&
    /^[0-9a-f-]{36}$/i.test(item.key) &&
    typeof item.digest === "string" &&
    /^[0-9a-f]{64}$/.test(item.digest) &&
    (item.expectedVersion === undefined ||
      (Number.isSafeInteger(item.expectedVersion) &&
        item.expectedVersion > 0)) &&
    Number.isFinite(item.createdAt) &&
    item.createdAt <= Date.now() &&
    Date.now() - item.createdAt < lifetime
  );
}
export async function pendingManualIntent(
  actorId: string,
  matterId: string,
  request: unknown,
): Promise<ManualIntent> {
  const digest = await fingerprint(request);
  return pending(actorId, matterId, "manual-intent", "", digest);
}

async function hash(bytes: BufferSource): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

async function fingerprint(request: unknown) {
  return hash(new TextEncoder().encode(JSON.stringify(canonical(request))));
}

export async function pendingOperationIntent(
  actorId: string,
  matterId: string,
  operation: string,
  request: unknown,
  expectedVersion?: number,
): Promise<ManualIntent> {
  if (
    !operation ||
    (expectedVersion !== undefined &&
      (!Number.isSafeInteger(expectedVersion) || expectedVersion < 1))
  )
    throw new Error("Operation and valid precondition required");
  return pending(
    actorId,
    matterId,
    "operation-intent",
    operation,
    await fingerprint(request),
    expectedVersion,
  );
}

/** Re-selecting a file retries its pending upload. A completed upload clears the key. */
export async function pendingUploadIntent(
  actorId: string,
  matterId: string,
  file: File,
): Promise<ManualIntent> {
  const digest = await fingerprint({
    bytes: await hash(await file.arrayBuffer()),
    name: file.name,
    type: file.type,
    size: file.size,
  });
  return pending(actorId, matterId, "upload-intent", digest, digest);
}

function pending(
  actorId: string,
  matterId: string,
  kind: string,
  operation: string,
  digest: string,
  expectedVersion?: number,
): ManualIntent {
  if (!actorId || !matterId)
    throw new Error("Authenticated actor and matter required");
  const storageKey = `draftly:${kind}:v1:${encodeURIComponent(actorId)}:${encodeURIComponent(matterId)}${operation ? `:${encodeURIComponent(operation)}` : ""}`;
  let stored: unknown,
    persistent = true;
  try {
    const raw = sessionStorage.getItem(storageKey);
    if (raw) {
      try {
        stored = JSON.parse(raw);
      } catch {
        sessionStorage.removeItem(storageKey);
      }
    }
  } catch {
    persistent = false;
  }
  const previous = valid(stored) ? stored : memory.get(storageKey);
  const metadata: Metadata =
    valid(previous) && previous.digest === digest
      ? previous
      : {
          version: 1,
          key: crypto.randomUUID(),
          digest,
          createdAt: Date.now(),
          ...(expectedVersion === undefined ? {} : { expectedVersion }),
        };
  memory.set(storageKey, metadata);
  try {
    sessionStorage.setItem(storageKey, JSON.stringify(metadata));
  } catch {
    persistent = false;
  }
  // Bound this tab's RAM fallback and discard expired actor/matter entries.
  for (const [key, item] of memory) if (!valid(item)) memory.delete(key);
  return { ...metadata, storageKey, persistent };
}
export function clearManualIntent(intent: ManualIntent) {
  if (memory.get(intent.storageKey)?.key === intent.key)
    memory.delete(intent.storageKey);
  try {
    const stored = JSON.parse(
      sessionStorage.getItem(intent.storageKey) ?? "null",
    ) as Metadata | null;
    if (stored?.key === intent.key)
      sessionStorage.removeItem(intent.storageKey);
  } catch {
    /* Disabled storage already has a visible RAM-fallback notice. */
  }
}

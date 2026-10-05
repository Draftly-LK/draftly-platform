import { readFile } from "node:fs/promises";
import path from "node:path";

/**
 * Development-only: serves a gazette page image from docs/reference so the
 * compare view can sit the rendered template beside the printed page. The
 * name is matched against a fixed pattern, so no other file is reachable.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ lang: string }> },
) {
  // The shared segment is the image name on this legacy one-segment URL.
  const { lang: name } = await params;
  if (
    process.env.NODE_ENV === "production" ||
    !/^page-\d{2}\.png$/.test(name)
  ) {
    return new Response(null, { status: 404 });
  }
  try {
    const file = await readFile(
      path.join(
        process.cwd(),
        "..",
        "docs",
        "reference",
        "forms",
        "pages",
        name,
      ),
    );
    return new Response(new Uint8Array(file), {
      headers: { "content-type": "image/png" },
    });
  } catch {
    return new Response(null, { status: 404 });
  }
}

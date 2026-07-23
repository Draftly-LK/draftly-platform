import { readFile } from "node:fs/promises";
import path from "node:path";
import { NextResponse } from "next/server";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ name: string }> },
) {
  if (process.env.NODE_ENV !== "development") {
    return new NextResponse("Not found", { status: 404 });
  }

  const { name } = await params;
  if (!/^page-\d{2}\.png$/.test(name)) {
    return new NextResponse("Invalid", { status: 400 });
  }

  const filePath = path.join(
    process.cwd(),
    "..",
    "docs",
    "reference",
    "forms",
    "pages",
    name,
  );

  try {
    const buf = await readFile(filePath);
    return new NextResponse(buf, {
      headers: {
        "Content-Type": "image/png",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    // fallback when cwd is repo root
    try {
      const alt = path.join(
        process.cwd(),
        "docs",
        "reference",
        "forms",
        "pages",
        name,
      );
      const buf = await readFile(alt);
      return new NextResponse(buf, {
        headers: {
          "Content-Type": "image/png",
          "Cache-Control": "no-store",
        },
      });
    } catch {
      return new NextResponse("Not found", { status: 404 });
    }
  }
}

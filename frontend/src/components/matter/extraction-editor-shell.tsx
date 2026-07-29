"use client";

import dynamic from "next/dynamic";

export const ExtractionEditor = dynamic(
  () => import("./extraction-editor"),
  { ssr: false, loading: () => null },
);

import { notFound } from "next/navigation";
import { GazetteCompare } from "@/components/gazette/gazette-compare";
import { GAZETTE_FORMS } from "@/lib/gazette-forms";
import { SINHALA_GAZETTE_FORMS } from "@/lib/gazette-forms/sinhala";

/**
 * Development-only: a gazette template beside the printed pages it transcribes.
 * The served (English) edition by default; `?lang=si` shows the Sinhala edition
 * that is kept apart from the application.
 */
export default async function GazetteComparePage({
  params,
  searchParams,
}: {
  params: Promise<{ form: string }>;
  searchParams: Promise<{ lang?: string }>;
}) {
  const { form } = await params;
  const { lang } = await searchParams;
  const set = lang === "si" ? SINHALA_GAZETTE_FORMS : GAZETTE_FORMS;
  const gazette = Object.values(set).find((candidate) => candidate.formNumber === form);
  if (process.env.NODE_ENV === "production" || !gazette) notFound();
  return <GazetteCompare gazette={gazette} />;
}

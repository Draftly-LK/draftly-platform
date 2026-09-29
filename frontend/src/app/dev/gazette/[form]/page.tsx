import { notFound } from "next/navigation";
import { GazetteCompare } from "@/components/gazette/gazette-compare";
import { GAZETTE_FORMS } from "@/lib/gazette-forms";

/** Development-only: a gazette template beside the printed pages it transcribes. */
export default async function GazetteComparePage({ params }: { params: Promise<{ form: string }> }) {
  const { form } = await params;
  const gazette = Object.values(GAZETTE_FORMS).find((candidate) => candidate.formNumber === form);
  if (process.env.NODE_ENV === "production" || !gazette) notFound();
  return <GazetteCompare templateId={gazette.templateId} />;
}

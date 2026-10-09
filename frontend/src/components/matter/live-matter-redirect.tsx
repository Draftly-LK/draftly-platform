"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
export function LiveMatterRedirect({
  matterId,
  section,
}: {
  matterId: string;
  section: "checks" | "documents";
}) {
  const router = useRouter();
  const t = useTranslations("matterNav");
  const href = `/matters/${encodeURIComponent(matterId)}/${section}`;
  useEffect(() => {
    router.replace(href);
  }, [router, href]);
  return (
    <p className="p-6" role="status">
      <Link className="text-link underline" href={href}>
        {t(section)}
      </Link>
    </p>
  );
}

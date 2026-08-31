import Image from "next/image";

/**
 * The Draftly typewriter mark.
 *
 * Decorative in every placement it has: the wordmark or the page heading
 * beside it already names the product, so alt text here would be announced
 * twice. If the mark is ever used alone, give that placement its own labelled
 * wrapper rather than adding alt text to this component.
 *
 * Two tones because the mark is flat: `blue` for canvas and surface, `white`
 * for the scrimmed photograph on the first-run and intake entry screens. The
 * source files are square and pre-trimmed, so `className` only has to set a
 * size (`size-8`, `size-12`, …).
 */
export function BrandMark({
  tone = "blue",
  className = "size-8",
  priority = false,
}: {
  tone?: "blue" | "white";
  className?: string;
  priority?: boolean;
}) {
  return (
    <Image
      src={`/images/logo-mark-${tone}.png`}
      alt=""
      aria-hidden="true"
      width={540}
      height={540}
      priority={priority}
      className={className}
    />
  );
}

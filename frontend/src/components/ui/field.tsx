import { CircleAlert } from "lucide-react";
import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { cn } from "@/lib/utils";

interface FieldCopy {
  label: ReactNode;
  /** Quiet guidance under the control. */
  help?: ReactNode;
  /** Replaces the help text. Shown with an icon so it never relies on colour. */
  error?: ReactNode;
}

/** Shared by every control: a 3:1 boundary, visible focus, and clear disabled / invalid states. */
const controlClasses =
  "block w-full min-h-10 border border-border-control bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted-ink hover:bg-hover-bg disabled:cursor-not-allowed disabled:border-border disabled:bg-disabled-bg disabled:text-disabled-fg read-only:bg-canvas aria-[invalid=true]:border-red [@media(pointer:coarse)]:min-h-11";

function useFieldIds(id: string | undefined, copy: FieldCopy) {
  const generated = useId();
  const controlId = id ?? generated;
  const helpId = copy.help && !copy.error ? `${controlId}-help` : undefined;
  const errorId = copy.error ? `${controlId}-error` : undefined;
  return { controlId, helpId, errorId, describedBy: errorId ?? helpId };
}

function FieldShell({
  controlId,
  helpId,
  errorId,
  copy,
  className,
  children,
}: {
  controlId: string;
  helpId?: string;
  errorId?: string;
  copy: FieldCopy;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={controlId} className="text-sm font-medium text-ink">
        {copy.label}
      </label>
      {children}
      {copy.error ? (
        <p id={errorId} className="flex items-start gap-1.5 text-sm text-red">
          <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" strokeWidth={1.5} />
          <span>{copy.error}</span>
        </p>
      ) : copy.help ? (
        <p id={helpId} className="text-compact text-muted-ink">
          {copy.help}
        </p>
      ) : null}
    </div>
  );
}

type InputProps = InputHTMLAttributes<HTMLInputElement> & FieldCopy & { wrapperClassName?: string };

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, help, error, id, className, wrapperClassName, ...props },
  ref,
) {
  const ids = useFieldIds(id, { label, help, error });
  return (
    <FieldShell {...ids} copy={{ label, help, error }} className={wrapperClassName}>
      <input
        ref={ref}
        id={ids.controlId}
        aria-invalid={error ? true : undefined}
        aria-describedby={ids.describedBy}
        className={cn(controlClasses, "rounded-control", className)}
        {...props}
      />
    </FieldShell>
  );
});

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & FieldCopy & { wrapperClassName?: string };

/** The chevron is drawn by globals.css (`select:not([multiple])`). */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, help, error, id, className, wrapperClassName, children, ...props },
  ref,
) {
  const ids = useFieldIds(id, { label, help, error });
  return (
    <FieldShell {...ids} copy={{ label, help, error }} className={wrapperClassName}>
      <select
        ref={ref}
        id={ids.controlId}
        aria-invalid={error ? true : undefined}
        aria-describedby={ids.describedBy}
        className={cn(controlClasses, "rounded-control", className)}
        {...props}
      >
        {children}
      </select>
    </FieldShell>
  );
});

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & FieldCopy & { wrapperClassName?: string };

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, help, error, id, className, wrapperClassName, ...props },
  ref,
) {
  const ids = useFieldIds(id, { label, help, error });
  return (
    <FieldShell {...ids} copy={{ label, help, error }} className={wrapperClassName}>
      <textarea
        ref={ref}
        id={ids.controlId}
        aria-invalid={error ? true : undefined}
        aria-describedby={ids.describedBy}
        className={cn(controlClasses, "min-h-24 rounded", className)}
        {...props}
      />
    </FieldShell>
  );
});

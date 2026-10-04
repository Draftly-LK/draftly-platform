import { CircleCheck, CircleDashed, TriangleAlert, type LucideIcon } from "lucide-react";
import type { StatusTone } from "@/lib/home/dashboard";

/** The icon that travels with each status tone, so a status is never colour alone. */
export const statusToneIcons: Record<StatusTone, LucideIcon> = {
  warning: TriangleAlert,
  danger: TriangleAlert,
  success: CircleCheck,
  info: CircleDashed,
  neutral: CircleDashed,
};

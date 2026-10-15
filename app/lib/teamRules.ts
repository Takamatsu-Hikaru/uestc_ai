import type { Competition } from "@/app/lib/domain";

// Competition rules are optional; an absent key means that rule is unlimited.
export function teamSizeLabel(config: Competition["config"] | undefined): string {
  const size = config?.team_size;
  if (!size) return "不限";
  return size.min === size.max ? `${size.min} 人` : `${size.min}–${size.max} 人`;
}

export function trackLimitLabel(config: Competition["config"] | undefined): string {
  const limit = config?.max_tracks;
  return typeof limit === "number" && limit > 0 ? `最多 ${limit} 条` : "不限";
}

export function ruleSummary(config: Competition["config"] | undefined): string {
  const parts: string[] = [];
  const size = config?.team_size;
  if (size) parts.push(`每队 ${size.min === size.max ? size.min : `${size.min}–${size.max}`} 人`);
  const limit = config?.max_tracks;
  if (typeof limit === "number" && limit > 0) parts.push(`每队最多报名 ${limit} 条赛道`);
  return parts.join("，");
}

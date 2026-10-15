"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ComponentProps } from "react";
import { api } from "@/app/lib/api";
import { fetchResource } from "@/app/lib/resourceCache";

export function PrefetchLink({ href, onMouseEnter, onFocus, ...props }: ComponentProps<typeof Link>) {
  const router = useRouter();
  function warm() {
    if (typeof href !== "string" || !href.startsWith("/") || href.startsWith("//")) return;
    const path = href.split(/[?#]/)[0];
    const problem = path.match(/\/(?:problems|submit)\/([^/]+)$/);
    const competition = path.match(/^\/competitions\/([^/]+)(?:\/tracks\/([^/]+))?$/);
    const resource = problem ? `/problems/${problem[1]}` : competition ? path : null;
    if (!resource) return;
    router.prefetch(href);
    void fetchResource(resource, () => api(resource)).catch(() => undefined);
  }
  return <Link {...props} href={href} onMouseEnter={(event) => { onMouseEnter?.(event); warm(); }}
    onFocus={(event) => { onFocus?.(event); warm(); }} />;
}

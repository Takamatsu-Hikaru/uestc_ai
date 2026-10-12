"use client";

import Link from "next/link";
import { ArrowRight, CalendarDays, Layers3 } from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { EmptyState, PageError, PageLoading, StatusPill } from "@/app/components/ui";
import type { Competition } from "@/app/lib/domain";
import { competitionSummary, WUJIE_SLUG } from "@/app/lib/wujiePresentation";
import { formatBeijing } from "@/app/lib/time";
import { useApiResource } from "@/app/lib/useApiResource";

function formatDate(value?: string | null) {
  return value ? formatBeijing(value, { year: "numeric", month: "2-digit", day: "2-digit" }) : "待公布";
}

export default function CompetitionsPage() {
  const { data, loading, error, reload } = useApiResource<Competition[]>("/competitions");
  return (
    <AppShell title="比赛" eyebrow="COMPETITIONS">
      <div className="page-intro"><p>AI 社首届「无界杯」UESTC AI 挑战赛，设置计算机视觉、Agent 和具身智能三个方向。</p></div>
      {loading ? <PageLoading /> : error ? <PageError message={error} retry={reload} /> : !data?.length ? <EmptyState title="暂无赛事" description="公开赛事会显示在这里。" /> : (
        <div className="competition-list">
          {data.map((competition, index) => (
            <Link className="competition-row" href={`/competitions/${competition.slug}`} key={competition.id}>
              {competition.slug === "wujie-cup-2026" && <img className="competition-list-poster" src="/visuals/wujie-poster.webp" alt="无界杯海报" width={1086} height={1448} />}<span className="competition-index">{String(index + 1).padStart(2, "0")}</span>
              <div className="competition-main"><StatusPill tone={competition.status === "published" ? "live" : "muted"}>{competition.status === "published" ? "开放" : competition.status}</StatusPill><h2>{competition.name}</h2><p>{competitionSummary(competition.slug, competition.summary)}</p></div>
              <div className="competition-meta">{competition.slug === WUJIE_SLUG ? <span>奖金 3,000 / 2,000 / 1,000 元</span> : <span><CalendarDays size={14} />{formatDate(competition.starts_at)} — {formatDate(competition.ends_at)}</span>}<span><Layers3 size={14} />{competition.tracks?.length ?? 0} 条赛道</span></div>
              <ArrowRight size={18} />
            </Link>
          ))}
        </div>
      )}
    </AppShell>
  );
}

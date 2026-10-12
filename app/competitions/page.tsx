"use client";

import Link from "next/link";
import { ArrowRight, CalendarDays, Layers3 } from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { EmptyState, PageError, PageLoading, StatusPill } from "@/app/components/ui";
import type { Competition } from "@/app/lib/domain";
import { formatBeijing } from "@/app/lib/time";
import { useApiResource } from "@/app/lib/useApiResource";

function formatDate(value?: string | null) {
  return value ? formatBeijing(value, { year: "numeric", month: "2-digit", day: "2-digit" }) : "待公布";
}

export default function CompetitionsPage() {
  const { data, loading, error, reload } = useApiResource<Competition[]>("/competitions");
  return (
    <AppShell title="比赛" eyebrow="COMPETITIONS">
      <div className="page-intro"><p>找到感兴趣的赛道，和队友一起把想法变成作品。赛事时间、题目与参赛规则，都从这里开始。</p></div>
      {loading ? <PageLoading /> : error ? <PageError message={error} retry={reload} /> : !data?.length ? <EmptyState title="暂无赛事" description="公开赛事会显示在这里。" /> : (
        <div className="competition-list">
          {data.map((competition, index) => (
            <Link className="competition-row" href={`/competitions/${competition.slug}`} key={competition.id}>
              <span className="competition-index">{String(index + 1).padStart(2, "0")}</span>
              <div className="competition-main"><StatusPill tone={competition.status === "published" ? "live" : "muted"}>{competition.status === "published" ? "开放" : competition.status}</StatusPill><h2>{competition.name}</h2><p>{competition.summary}</p></div>
              <div className="competition-meta"><span><CalendarDays size={14} />{formatDate(competition.starts_at)} — {formatDate(competition.ends_at)}</span><span><Layers3 size={14} />赛道进入后查看题目</span></div>
              <ArrowRight size={18} />
            </Link>
          ))}
        </div>
      )}
    </AppShell>
  );
}

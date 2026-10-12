"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowRight, CalendarDays, Users } from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { CompetitionPoster, TrackVisual, trackSummary } from "@/app/components/ClubVisuals";
import { competitionSummary, competitionOverview, trackName, trackDirection, WUJIE_SLUG } from "@/app/lib/wujiePresentation";
import { WujieAudience, WujieTaskDocuments, WujiePrizes } from "@/app/components/WujieIntroduction";
import { Markdown } from "@/app/components/Markdown";
import { PageError, PageLoading, StatusPill } from "@/app/components/ui";
import type { Competition } from "@/app/lib/domain";
import { formatBeijing } from "@/app/lib/time";
import { useApiResource } from "@/app/lib/useApiResource";

function date(value?: string | null) {
  return value ? formatBeijing(value, { year: "numeric", month: "long", day: "numeric" }) : "待公布";
}

export default function CompetitionPage() {
  const params = useParams<{ competitionSlug: string }>();
  const slug = params.competitionSlug;
  const { data, loading, error, reload } = useApiResource<Competition>(slug ? `/competitions/${slug}` : null);
  return (
    <AppShell variant="detail" title={data?.name ?? "赛事详情"} eyebrow="COMPETITION" actions={<Link className="primary-button compact-button" href="/dashboard"><Users size={15} />组队与报名</Link>}>
      {loading ? <PageLoading /> : error || !data ? <PageError message={error || "赛事不存在。"} retry={reload} /> : (
        <>
          <section className="competition-overview">{data.slug === "wujie-cup-2026" && <CompetitionPoster />}
            <div><StatusPill tone={data.status === "draft" ? "warm" : "live"}>{data.status === "published" ? "已发布" : data.status === "draft" ? "筹备草稿" : data.status}</StatusPill><p>{competitionSummary(data.slug, data.summary)}</p>{data.slug === WUJIE_SLUG && <WujieAudience />}</div>
            {data.slug !== WUJIE_SLUG && <dl className="date-grid">
              <div><dt>报名开放</dt><dd>{date(data.registration_opens_at)}</dd></div>
              <div><dt>报名截止</dt><dd>{date(data.registration_closes_at)}</dd></div>
              <div><dt>比赛开始</dt><dd>{date(data.starts_at)}</dd></div>
              <div><dt>比赛结束</dt><dd>{date(data.ends_at)}</dd></div>
            </dl>}
          </section>
          <section className="content-section">
            <header className="section-header"><div><span className="eyebrow"><i />TRACKS</span><h2>比赛赛道</h2></div></header>
            <div className="track-directory">
              {(data.tracks ?? []).map((track, index) => (
                <article className="track-with-document" key={track.id}><Link className="track-entry" href={`/competitions/${data.slug}/tracks/${track.slug}`}>
                  <TrackVisual value={track.slug} /><span className="track-number">{String(index + 1).padStart(2, "0")}</span>
                  <div><small>{trackDirection(track.slug, track.config?.short ?? "TRACK")}</small><h3>{trackName(track.slug, track.name)}</h3><p>{trackSummary(track.slug, track.description)}</p></div>
                  <span className="track-count">{track.problems?.length ?? 0} 个题目</span>
                  <ArrowRight size={18} />
                </Link>{data.slug === WUJIE_SLUG && <WujieTaskDocuments trackSlug={track.slug} />}</article>
              ))}
            </div>
          </section>
          {data.slug === WUJIE_SLUG && <WujiePrizes />}
          {data.config.overview_md && <section className="content-section competition-rules" aria-label="赛事介绍与细则"><Markdown>{competitionOverview(data.slug, data.config.overview_md)}</Markdown></section>}
          <section className="rule-band">
            <CalendarDays size={19} />
            <div><strong>通用参赛流程</strong><p>创建队伍 → 报名赛道 → 阅读题目 → 提交 README 与作品材料 → 按版本评审。</p></div>
            <Link href="/dashboard">打开工作台 <ArrowRight size={15} /></Link>
          </section>
        </>
      )}
    </AppShell>
  );
}

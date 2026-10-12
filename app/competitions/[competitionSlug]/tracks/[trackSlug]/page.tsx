"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, ArrowRight, Cpu, Gauge } from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { EmptyState, PageError, PageLoading, StatusPill } from "@/app/components/ui";
import type { Track } from "@/app/lib/domain";
import { useApiResource } from "@/app/lib/useApiResource";

export default function TrackPage() {
  const params = useParams<{ competitionSlug: string; trackSlug: string }>();
  const { competitionSlug, trackSlug } = params;
  const { data, loading, error, reload } = useApiResource<Track>(competitionSlug && trackSlug ? `/competitions/${competitionSlug}/tracks/${trackSlug}` : null);
  return (
    <AppShell variant="detail" title={data?.name ?? "赛道"} eyebrow="TRACK" actions={<Link className="outline-button" href={`/competitions/${competitionSlug}`}><ArrowLeft size={15} />返回赛事</Link>}>
      {loading ? <PageLoading /> : error || !data ? <PageError message={error || "赛道不存在。"} retry={reload} /> : (
        <>
          <section className="track-overview"><div><span className="mono-label">{data.config?.short ?? data.slug.toUpperCase()}</span><p>{data.description}</p></div><dl><div><dt>题目数量</dt><dd>{data.problems?.length ?? 0}</dd></div><div><dt>参赛方式</dt><dd>个人 / 组队</dd></div></dl></section>
          <section className="content-section">
            <header className="section-header"><div><span className="eyebrow"><i />PROBLEMS</span><h2>赛道题目</h2></div><span className="section-note">点入题目后查看规则、资源与提交要求</span></header>
            {!data.problems?.length ? <EmptyState title="暂无公开题目" description="赛题发布后会显示在这里。" /> : <div className="problem-directory">
              {data.problems.map((problem) => (
                <Link key={problem.id} href={`/competitions/${competitionSlug}/tracks/${trackSlug}/problems/${problem.slug}`}>
                  <span className="problem-code-block">{problem.code}</span>
                  <div><div className="problem-heading"><h3>{problem.title}</h3><StatusPill tone={problem.status === "published" ? "live" : "warm"}>{problem.status === "published" ? "正式" : "候选"}</StatusPill></div><p>{problem.summary}</p><span className="problem-facts"><i><Gauge size={13} />难度 {problem.difficulty}/5</i><i><Cpu size={13} />{problem.compute_note}</i></span></div>
                  <ArrowRight size={18} />
                </Link>
              ))}
            </div>}
          </section>
        </>
      )}
    </AppShell>
  );
}

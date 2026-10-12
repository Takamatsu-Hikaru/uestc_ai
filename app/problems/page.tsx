"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowRight, Search } from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { EmptyState, PageError, PageLoading, StatusPill } from "@/app/components/ui";
import type { Problem, Track } from "@/app/lib/domain";
import { useApiResource } from "@/app/lib/useApiResource";

type ProblemListing = Problem & { track: Track; competition_slug: string };

export default function ProblemsPage() {
  const { data, loading, error, reload } = useApiResource<ProblemListing[]>("/problems");
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (data ?? []).filter((item) => !needle || `${item.code} ${item.title} ${item.summary} ${item.track.name}`.toLowerCase().includes(needle));
  }, [data, query]);
  return (
    <AppShell title="题库" eyebrow="PROBLEM LIBRARY">
      <div className="page-intro with-search"><p>跨赛事浏览公开赛题。候选题用于社内调研，正式题目开放报名与提交。</p><label className="search-field"><Search size={16} /><span className="sr-only">搜索题目</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索编号、题目或赛道" /></label></div>
      {loading ? <PageLoading /> : error ? <PageError message={error} retry={reload} /> : !filtered.length ? <EmptyState title="没有匹配题目" description="试试更短的关键词。" /> : (
        <div className="problem-directory standalone">{filtered.map((problem) => (
          <Link key={problem.id} href={`/competitions/${problem.competition_slug}/tracks/${problem.track.slug}/problems/${problem.slug}`}>
            <span className="problem-code-block">{problem.code}</span>
            <div><div className="problem-heading"><h3>{problem.title}</h3><StatusPill tone={problem.status === "published" ? "live" : "warm"}>{problem.status === "published" ? "正式" : "候选"}</StatusPill></div><p>{problem.summary}</p><span className="problem-facts"><i>{problem.track.name}</i><i>难度 {problem.difficulty}/5</i></span></div>
            <ArrowRight size={18} />
          </Link>
        ))}</div>
      )}
    </AppShell>
  );
}


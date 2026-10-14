"use client";

import { useEffect, useState } from "react";
import type { EvaluationRun } from "@/app/lib/domain";
import { evaluationTiming, formatEvaluationDuration, formatEvaluationLimit } from "@/app/lib/evaluation-timing";
import { formatBeijing } from "@/app/lib/time";

function displayTime(value: number | null) {
  return value === null ? "—" : formatBeijing(new Date(value), { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function EvaluationTiming({ run }: { run: EvaluationRun }) {
  const [now, setNow] = useState<number | null>(null);
  const active = run.status === "queued" || run.status === "running";
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  const timing = evaluationTiming(run, now);
  return <div className="evaluation-timing" aria-label="测试时间信息">
    <dl className="evaluation-timing-summary">
      <div><dt>本次运行上限</dt><dd>{formatEvaluationLimit(run.time_seconds)}</dd></div>
      <div><dt>{timing.retried ? "领取前累计耗时" : "排队耗时"}</dt><dd>{timing.waitSeconds === null && run.status === "queued" ? "等待领取" : formatEvaluationDuration(timing.waitSeconds)}</dd></div>
      <div><dt>处理耗时<span>含准备与收尾</span></dt><dd>{timing.started === null ? "尚未开始" : timing.processingSeconds === null && active ? "计时中…" : formatEvaluationDuration(timing.processingSeconds)}</dd></div>
    </dl>
    <div className="evaluation-timing-dates">
      <span>入队 <time dateTime={timing.created === null ? undefined : run.created_at}>{displayTime(timing.created)}</time></span>
      {timing.started !== null && <span>{timing.retried ? "本轮开始处理" : "开始处理"} <time dateTime={run.started_at ?? undefined}>{displayTime(timing.started)}</time></span>}
      {timing.finished !== null && <span>结束 <time dateTime={run.finished_at ?? undefined}>{displayTime(timing.finished)}</time></span>}
    </div>
    <p className="evaluation-timing-note">排队不占运行时限；环境启动与全部场景共用本次上限。{timing.retried ? "本任务已重新领取，领取前累计耗时包含先前尝试。" : ""}</p>
  </div>;
}

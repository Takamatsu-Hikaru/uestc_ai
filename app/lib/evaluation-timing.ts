import type { EvaluationRun } from "@/app/lib/domain";

type TimedRun = Pick<EvaluationRun, "status" | "attempts" | "created_at" | "started_at" | "finished_at">;

function timestamp(value: string | null): number | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function secondsBetween(start: number | null, end: number | null): number | null {
  return start === null || end === null ? null : Math.max(0, Math.floor((end - start) / 1000));
}

export function evaluationTiming(run: TimedRun, now: number | null = null) {
  const created = timestamp(run.created_at);
  const started = timestamp(run.started_at);
  const finished = timestamp(run.finished_at);
  const active = run.status === "queued" || run.status === "running";
  const end = finished ?? (active && now !== null && Number.isFinite(now) ? now : null);
  return {
    created, started, finished, active,
    retried: run.attempts > 1,
    waitSeconds: secondsBetween(created, started ?? end),
    processingSeconds: secondsBetween(started, end),
  };
}

export function formatEvaluationDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return "—";
  const whole = Math.floor(seconds);
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor(whole % 3600 / 60);
  const remainder = whole % 60;
  return [hours ? `${hours} 小时` : "", minutes ? `${minutes} 分` : "", `${remainder} 秒`].filter(Boolean).join(" ");
}

export function formatEvaluationLimit(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds <= 0) return "—";
  return seconds % 60 === 0 ? `${seconds / 60} 分钟（${seconds} 秒）` : `${seconds} 秒`;
}

export function evaluationStatus(run: Pick<EvaluationRun, "status" | "error">): string {
  if (run.status === "failed") return run.error === "evaluation time limit exceeded" ? "已超时" : "测试失败";
  return { queued: "排队中", running: "测试中", completed: "已完成", superseded: "旧提交记录" }[run.status];
}

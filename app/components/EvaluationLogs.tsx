"use client";

import { useEffect, useRef, useState } from "react";
import { Download, RefreshCw } from "lucide-react";
import { api, resolveMarkdownUrl } from "@/app/lib/api";
import type { EvaluationRun } from "@/app/lib/domain";

type LogStream = { id: string; source: string; attempt: number; name: string; size: number; url: string };
type LogChunk = { text: string; offset: number; size: number };
const labels: Record<string, string> = { worker: "运行进度", agent: "程序输出", controller: "环境输出", diagnostics: "异常堆栈", environment: "环境附加日志" };
const MAX_DISPLAY = 1024 * 1024;

export function EvaluationLogs({ run }: { run: EvaluationRun }) {
  const [open, setOpen] = useState(false);
  const [streams, setStreams] = useState<LogStream[]>([]);
  const [chosenId, setChosenId] = useState("");
  const [view, setView] = useState({ id: "", text: "", clipped: false });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const output = useRef<HTMLPreElement>(null);
  const selected = streams.find(item => item.id === chosenId) ?? streams.at(-1);
  const selectedId = selected?.id;
  const active = run.status === "queued" || run.status === "running";

  useEffect(() => {
    if (!open) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function update() {
      try {
        const result = await api<{ items: LogStream[] }>(`/evaluation-runs/${run.id}/logs`);
        if (alive) { setStreams(result.items); setError(""); }
      } catch { if (alive) setError("日志暂时无法读取，请刷新重试。"); }
      if (alive && active) timer = setTimeout(update, 3000);
    }
    void update();
    return () => { alive = false; clearTimeout(timer); };
  }, [run.id, open, active, refresh]);

  useEffect(() => {
    if (!open || !selectedId) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let offset = 0;
    let text = "";
    let clipped = false;
    const streamId = selectedId;
    async function update() {
      if (alive) setLoading(true);
      try {
        const chunk = await api<LogChunk>(`/evaluation-logs/${streamId}?offset=${offset}`);
        if (!alive) return;
        const follow = !output.current || output.current.scrollHeight - output.current.scrollTop - output.current.clientHeight < 40;
        offset = chunk.offset;
        text += chunk.text;
        if (text.length > MAX_DISPLAY) { text = text.slice(-MAX_DISPLAY); clipped = true; }
        setView({ id: streamId, text, clipped });
        setError("");
        if (follow) requestAnimationFrame(() => { if (alive && output.current) output.current.scrollTop = output.current.scrollHeight; });
        if (offset < chunk.size) timer = setTimeout(update, 50);
        else if (active) timer = setTimeout(update, 3000);
      } catch { if (alive) { setError("日志暂时无法读取，请刷新重试。"); if (active) timer = setTimeout(update, 3000); } }
      finally { if (alive) setLoading(false); }
    }
    void update();
    return () => { alive = false; clearTimeout(timer); };
  }, [open, selectedId, active, refresh]);

  return <section className="evaluation-log-panel" aria-label="测评日志">
    <button type="button" className="evaluation-log-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>测评日志<span>{open ? "收起" : "查看输出与诊断"}</span></button>
    {open && <div className="evaluation-log-body">
      <div className="evaluation-log-tools"><label>日志来源<select value={selected?.id ?? ""} onChange={event => setChosenId(event.target.value)} aria-label="日志来源">{streams.map(stream => <option value={stream.id} key={stream.id}>第 {stream.attempt} 次执行 · {labels[stream.source] ?? stream.source}</option>)}</select></label><button type="button" className="text-button" disabled={loading} onClick={() => setRefresh(refresh + 1)}><RefreshCw size={14} />刷新</button>{selected && <a href={resolveMarkdownUrl(selected.url)} className="text-button"><Download size={14} />下载完整日志</a>}</div>
      {error && <p role="alert">{error}</p>}
      {!selected ? <p>{active ? "尚未收到日志；工作端开始运行后会自动更新。" : "这条记录尚未保存日志。"}</p> : <>
        <pre ref={output} tabIndex={0} aria-label={`${labels[selected.source] ?? selected.source}内容`}>{view.id === selected.id ? view.text || (loading ? "正在读取…" : "暂时没有输出。") : "正在读取…"}</pre>
        {view.id === selected.id && view.clipped && <small>屏幕展示最近 1 MiB 内容，可下载完整日志。</small>}
      </>}
      {active && <small>运行中每 3 秒自动更新；输出不会影响测试次数。</small>}
    </div>}
  </section>;
}

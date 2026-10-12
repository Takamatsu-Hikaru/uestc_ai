"use client";
import { type FormEvent, useState } from "react";
import { api, formatApiError, jsonBody } from "@/app/lib/api";
import { useApiResource } from "@/app/lib/useApiResource";
import { useToast } from "./ToastProvider";
import { FieldError, PageError, PageLoading } from "./ui";
import type { ComputeConfig, ComputeProvider } from "@/app/lib/compute";
import { ComputeConfigFields, defaultComputeConfig } from "./ComputeConfigFields";
import { ManualComputeAccountEditor } from "./ManualComputeAccountEditor";

export function ComputeQuotaEditor({ problemId }: { problemId: string }) {
  const endpoint = `/compute/manage/problems/${problemId}/quota`;
  const policy = useApiResource<{ config: ComputeConfig | null; team_count: number }>(endpoint);
  const channels = useApiResource<ComputeProvider[]>("/compute/manage/providers");
  if ((policy.loading && !policy.data) || (channels.loading && !channels.data)) return <PageLoading />;
  if (policy.error || channels.error) return <PageError message={policy.error || channels.error} retry={async () => { await policy.reload(); await channels.reload(); }} />;
  return <section className="ai-platform" aria-label="本题统一算力资源">
    <div className="ai-section-title"><div><h2>队伍自用算力</h2><p>选择平台托管实例或手动发放账号；自动指标测评的时长、次数和测评池独立配置。</p></div><span>{policy.data?.team_count ?? 0} 支队伍</span></div>
    <ComputeQuotaForm key={JSON.stringify(policy.data?.config)} config={policy.data?.config ?? null} channels={channels.data ?? []} endpoint={endpoint} reload={policy.reload} />
    {policy.data?.config?.mode === "manual_account" && <ManualComputeAccountEditor problemId={problemId} />}
  </section>;
}

function ComputeQuotaForm({ config, channels, endpoint, reload }: { config: ComputeConfig | null; channels: ComputeProvider[]; endpoint: string; reload: () => Promise<void> }) {
  const [value, setValue] = useState<ComputeConfig>(config ?? defaultComputeConfig());
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const toast = useToast();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await api(endpoint, { method: "PUT", ...jsonBody(value) });
      await reload(); toast.success("本题算力发放方式已保存");
    } catch (e) { setError(formatApiError(e)); } finally { setBusy(false); }
  }
  return <form className="ai-form-panel" onSubmit={submit}>
    <div className="ai-section-title"><h3>算力发放配置</h3><label className="ai-check"><input type="checkbox" checked={value.enabled} onChange={e => setValue({ ...value, enabled: e.target.checked })} />启用本题算力</label></div>
    <ComputeConfigFields value={value} onChange={setValue} providers={channels} />
    <FieldError>{error}</FieldError><button className="primary-button" disabled={busy}>{busy ? "正在保存…" : "保存本题算力配置"}</button>
  </form>;
}

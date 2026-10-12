"use client";

import Link from "next/link";
import type { ComputeConfig, ManagedComputeConfig } from "@/app/lib/compute";

type ProviderOption = { id: string; name: string; gpu_label: string; gpu_count: number; enabled: boolean };
export const defaultComputeConfig = (): ManagedComputeConfig => ({
  mode: "managed", provider_id: "", enabled: true, max_gpu_seconds: 36000, max_cost_millis: null,
});

export function ComputeConfigFields({ value, onChange, providers }: {
  value: ComputeConfig; onChange: (config: ComputeConfig) => void; providers: ProviderOption[];
}) {
  const manual = value.mode === "manual_account";
  return <div className="compute-config-fields">
    <label className="form-field"><span>算力发放方式</span><select value={value.mode ?? "managed"} onChange={e => onChange(e.target.value === "manual_account"
      ? { mode: "manual_account", enabled: value.enabled, login_url: "https://www.autodl.com/login", instructions: "" }
      : { ...defaultComputeConfig(), enabled: value.enabled, provider_id: providers[0]?.id ?? "" })}>
      <option value="managed">平台托管实例 · API 创建与计量</option>
      <option value="manual_account">手动发放 AutoDL 账号</option>
    </select></label>
    {manual ? <>
      <label className="form-field"><span>AutoDL 登录地址</span><input type="url" required value={value.login_url} onChange={e => onChange({ ...value, login_url: e.target.value })} /></label>
      <label className="form-field"><span>统一使用说明（可选）</span><textarea rows={3} maxLength={4000} value={value.instructions} onChange={e => onChange({ ...value, instructions: e.target.value })} placeholder="例如可用卡型、账号侧预算和训练镜像的使用方法。" /></label>
      <p className="evaluation-note">保存后可按队伍发放账号。队伍登录 AutoDL 自行创建和使用实例，费用及限额在 AutoDL 账号侧管理。平台不创建实例、不计量卡时，也不自动关机。组织方指标测评池仍单独配置。</p>
    </> : <>
      <label className="form-field"><span>算力渠道与类型</span><select required value={value.provider_id} onChange={e => onChange({ ...value, provider_id: e.target.value })}>
        <option value="">选择算力渠道…</option>{providers.map(p => <option key={p.id} value={p.id}>{p.name} · {p.gpu_label} × {p.gpu_count}{p.enabled ? "" : " · 已停用"}</option>)}
      </select></label>
      {!providers.length && <p className="evaluation-note">托管实例需要先在 <Link href="/api-platform">API 平台 → 算力渠道</Link> 添加 AutoDL API 渠道；手动发放账号无需配置渠道 Token。</p>}
      <div className="form-grid"><label className="form-field"><span>每队 GPU 卡时</span><input type="number" min={0} step="any" required value={value.max_gpu_seconds / 3600} onChange={e => onChange({ ...value, max_gpu_seconds: Math.round(Number(e.target.value) * 3600) })} /></label>
        <label className="form-field"><span>每队参考运行费用 · 元（可选）</span><input type="number" min={0} step="any" value={value.max_cost_millis == null ? "" : value.max_cost_millis / 1000} onChange={e => onChange({ ...value, max_cost_millis: e.target.value === "" ? null : Math.round(Number(e.target.value) * 1000) })} placeholder="留空不限制" /></label></div>
      <p className="evaluation-note">队伍在 API 平台开机并获取 SSH、JupyterLab 等工具。平台预占预算、计量卡时，到时自动关机。保存配置不会创建或启动实例。</p>
    </>}
  </div>;
}

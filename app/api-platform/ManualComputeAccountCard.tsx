"use client";

import { useEffect, useState } from "react";
import { ExternalLink, KeyRound } from "lucide-react";
import { api, formatApiError } from "@/app/lib/api";
import { copyText } from "@/app/lib/clipboard";
import type { ComputeAccountCredentials, ManualComputeAccount } from "@/app/lib/compute";
import { useToast } from "@/app/components/ToastProvider";
import { FieldError } from "@/app/components/ui";

export function ManualComputeAccountCard({ account, allowCredentials }: { account: ManualComputeAccount; allowCredentials: boolean }) {
  const [credentials, setCredentials] = useState<ComputeAccountCredentials | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const toast = useToast();
  useEffect(() => { if (!credentials) return; const timer = setTimeout(() => setCredentials(null), 60000); return () => clearTimeout(timer); }, [credentials]);
  async function reveal() {
    setError(""); setBusy(true);
    try { setCredentials(await api<ComputeAccountCredentials>(`/compute/accounts/${account.id}/credentials`, { method: "POST", cache: "no-store" })); }
    catch (e) { setCredentials(null); setError(formatApiError(e)); } finally { setBusy(false); }
  }
  return <article className="compute-resource manual-account-card">
    <div className="ai-quota-card"><div className="ai-card-heading"><div><small>{account.competition_name}</small><h3>{account.team_name}</h3></div><span className={`ai-badge ${account.status === "issued" ? "ok" : "off"}`}>{account.status === "issued" ? "账号已发放" : account.status === "paused" ? "已暂停" : "待发放"}</span></div>
      <p className="ai-grant-scope">{account.problem_title}</p><div className="ai-card-foot"><span>AutoDL 手动账号</span><span>账号侧管理算力</span></div></div>
    <div className="compute-controls">
      <p>{account.status === "pending" ? "组织方尚未发放账号，发放后可在这里查看。" : account.status === "paused" ? "账号查看入口已暂停，请联系组织方。" : "登录 AutoDL 自行使用算力，平台不托管训练实例。"}</p>
      {account.instructions && <p className="manual-account-notes">{account.instructions}</p>}
      <FieldError>{error}</FieldError>
      {account.status === "issued" && <div className="ai-button-row"><a className="outline-button" href={account.login_url} target="_blank" rel="noreferrer">前往 AutoDL<ExternalLink size={14} /></a>{allowCredentials && <button className="outline-button" disabled={busy} onClick={() => void reveal()}><KeyRound size={14} />{busy ? "读取中…" : "查看本队账号"}</button>}</div>}
      {credentials && account.status === "issued" && allowCredentials && <div className="compute-ssh">
        <label className="form-field"><span>AutoDL 账号</span><input readOnly value={credentials.username} autoComplete="off" /></label>
        <label className="form-field"><span>密码</span><input type="password" readOnly value={credentials.password} autoComplete="off" /></label>
        {credentials.notes && <p className="manual-account-notes">{credentials.notes}</p>}
        <div className="ai-button-row">{([ ["复制账号", credentials.username], ["复制密码", credentials.password] ] as const).map(([label, value]) => <button className="outline-button" key={label} onClick={async () => { try { await copyText(value); toast.success(label + "成功"); } catch { toast.error("复制失败，请稍后再试"); } }}>{label}</button>)}<button className="text-button" onClick={() => setCredentials(null)}>隐藏账号</button></div>
        <small>账号信息一分钟后自动隐藏。</small>
      </div>}
    </div>
  </article>;
}

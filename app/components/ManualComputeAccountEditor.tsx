"use client";

import { useState, type FormEvent } from "react";
import { api, formatApiError, jsonBody } from "@/app/lib/api";
import type { ComputeAccountCredentials, ManualComputeAccount } from "@/app/lib/compute";
import { useApiResource } from "@/app/lib/useApiResource";
import { useSession } from "./SessionProvider";
import { useToast } from "./ToastProvider";
import { EmptyState, FieldError, PageError, PageLoading } from "./ui";

export function ManualComputeAccountEditor({ problemId }: { problemId: string }) {
  const endpoint = `/compute/manage/problems/${problemId}/accounts`;
  const resource = useApiResource<ManualComputeAccount[]>(endpoint);
  const { user } = useSession();
  const [editing, setEditing] = useState<ManualComputeAccount | null>(null);
  const [initial, setInitial] = useState<ComputeAccountCredentials | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const toast = useToast();
  async function edit(account: ManualComputeAccount) {
    setError(""); setBusy(true); setInitial(null); setEditing(null);
    try {
      // Paused credentials are deliberately unavailable; replacement can still be issued.
      if (account.id && account.status === "issued") {
        const credentials = await api<ComputeAccountCredentials>(`/compute/accounts/${account.id}/credentials`, { method: "POST", cache: "no-store" });
        setInitial({ ...credentials, password: "" });
      }
      setEditing(account);
    } catch (e) { setError(formatApiError(e)); } finally { setBusy(false); }
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!editing || busy) return;
    const form = new FormData(event.currentTarget); setBusy(true); setError("");
    try {
      await api(`${endpoint}/${editing.team_id}`, { method: "PUT", ...jsonBody({ username: form.get("username"), password: form.get("password"), notes: form.get("notes"), enabled: true }) });
      setEditing(null); setInitial(null); await resource.reload(); toast.success("账号已发放给队伍");
    } catch (e) { setError(formatApiError(e)); } finally { setBusy(false); }
  }
  async function toggle(account: ManualComputeAccount) {
    setBusy(true); setError("");
    try {
      await api(`${endpoint}/${account.team_id}`, { method: "PATCH", ...jsonBody({ enabled: !account.account_enabled }) });
      await resource.reload(); toast.success(account.account_enabled ? "账号查看已停用" : "账号查看已启用");
    } catch (e) { setError(formatApiError(e)); } finally { setBusy(false); }
  }
  return <section className="manual-account-editor evaluation-editor" aria-label="手动发放队伍账号">
    <div className="ai-section-title"><div><h2>队伍账号发放</h2><p>账号仅本队成员与管理员可查看。停用只关闭平台查看入口；外部账号需在 AutoDL 侧调整。</p></div><button type="button" className="outline-button" onClick={() => void resource.reload()} disabled={busy}>刷新</button></div>
    <FieldError>{error}</FieldError>{resource.loading && !resource.data && <PageLoading />}{resource.error && <PageError message={resource.error} retry={resource.reload} />}
    {editing && <form className="ai-form-panel" onSubmit={save} key={editing.team_id}>
      <h3>{editing.team_name} · {editing.id ? "更新账号" : "发放账号"}</h3>
      <div className="form-grid"><label className="form-field"><span>AutoDL 账号</span><input name="username" required maxLength={200} autoComplete="off" defaultValue={initial?.username ?? ""} /></label>
        <label className="form-field"><span>密码{editing.id ? "（留空保留原密码）" : ""}</span><input name="password" type="password" required={!editing.id} maxLength={512} autoComplete="new-password" /></label></div>
      <label className="form-field"><span>本队使用备注（可选）</span><textarea name="notes" rows={3} maxLength={4000} defaultValue={initial?.notes ?? ""} /></label>
      <div className="ai-button-row"><button className="primary-button" disabled={busy}>保存并发放</button><button type="button" className="outline-button" disabled={busy} onClick={() => { setEditing(null); setInitial(null); }}>取消</button></div>
    </form>}
    {resource.data?.length ? <div className="ai-table-wrap"><table className="ai-table"><thead><tr><th>队伍</th><th>发放状态</th><th>更新时间</th>{user?.role === "admin" && <th>操作</th>}</tr></thead><tbody>{resource.data.map(account => <tr key={account.team_id}>
      <td>{account.team_name}</td><td>{account.status === "issued" ? "已发放" : account.status === "paused" ? "已暂停" : "待发放"}</td><td>{account.updated_at ? new Date(account.updated_at).toLocaleString("zh-CN") : "—"}</td>
      {user?.role === "admin" && <td><div className="ai-button-row"><button type="button" className="outline-button" disabled={busy} onClick={() => void edit(account)}>{account.id ? "更新账号" : "发放账号"}</button>{account.id && <button type="button" className="text-button" disabled={busy} onClick={() => void toggle(account)}>{account.account_enabled ? "停用查看" : "启用查看"}</button>}</div></td>}
    </tr>)}</tbody></table></div> : resource.data && <EmptyState title="尚无队伍" description="赛事队伍建立后，可在这里逐队发放 AutoDL 账号。" />}
  </section>;
}

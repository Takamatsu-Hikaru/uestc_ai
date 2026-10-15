"use client";

import { FormEvent, useEffect, useState } from "react";
import { Mail, Send } from "lucide-react";
import { AdminTabs } from "@/app/components/AdminTabs";
import { AppShell } from "@/app/components/AppShell";
import { useSession } from "@/app/components/SessionProvider";
import { useToast } from "@/app/components/ToastProvider";
import { FieldError, PageError, PageLoading, StatusPill } from "@/app/components/ui";
import { api, formatApiError, jsonBody } from "@/app/lib/api";
import type { MailSettings, MailTestResult } from "@/app/lib/domain";
import { formatBeijing } from "@/app/lib/time";
import { useApiResource } from "@/app/lib/useApiResource";

const sourceLabels: Record<MailSettings["source"], string> = {
  database: "后台配置",
  environment: "环境变量",
  none: "未配置",
};

// Reasons come back inside a successful test response, so they are translated here.
const reasonLabels: Record<string, string> = {
  "email delivery is not configured": "通道还不完整：缺少发件人或密钥。",
  "email provider rejected the request": "邮件服务拒绝了这封邮件。",
  "email provider is unavailable": "无法连接邮件服务，请检查地址、端口和网络。",
  "email settings cannot be decrypted": "已保存的配置无法解密，请重新保存密钥。",
  "email settings are invalid": "配置不完整或包含非法字符。",
};

function describeReason(reason: string) {
  return reasonLabels[reason] ?? reason ?? "发送失败。";
}

export default function AdminMailPage() {
  const { user, loading: sessionLoading } = useSession();
  const toast = useToast();
  const allowed = user?.role === "admin";
  const { data, loading, error, reload } = useApiResource<MailSettings>(allowed ? "/manage/mail" : null);
  const [provider, setProvider] = useState<MailSettings["provider"]>("resend");
  const [sender, setSender] = useState("");
  const [fallback, setFallback] = useState(false);
  const [resendSecret, setResendSecret] = useState("");
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState("465");
  const [smtpSecurity, setSmtpSecurity] = useState<"ssl" | "starttls">("ssl");
  const [smtpUsername, setSmtpUsername] = useState("");
  const [smtpSecret, setSmtpSecret] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [recipient, setRecipient] = useState("");
  const [testing, setTesting] = useState(false);
  const [testError, setTestError] = useState("");
  const [result, setResult] = useState<MailTestResult | null>(null);

  useEffect(() => {
    if (!data) return;
    setProvider(data.provider);
    setSender(data.sender);
    setFallback(data.fallback);
    setSmtpHost(data.smtp.host);
    setSmtpPort(data.smtp.port ? String(data.smtp.port) : "465");
    setSmtpSecurity(data.smtp.security === "starttls" ? "starttls" : "ssl");
    setSmtpUsername(data.smtp.username);
    setResendSecret("");
    setSmtpSecret("");
  }, [data]);

  // Blank secrets mean "keep the saved value", so the draft always carries them.
  function draft() {
    return {
      provider,
      sender,
      fallback,
      resend_secret: resendSecret,
      smtp_host: smtpHost,
      smtp_port: Number(smtpPort) || 0,
      smtp_security: smtpSecurity,
      smtp_username: smtpUsername,
      smtp_secret: smtpSecret,
    };
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setFormError("");
    try {
      await api<MailSettings>("/manage/mail", { method: "PUT", ...jsonBody(draft()) });
      setResendSecret("");
      setSmtpSecret("");
      await reload();
      toast.success("邮件通道已保存");
    } catch (requestError) {
      setFormError(formatApiError(requestError));
    } finally {
      setSaving(false);
    }
  }

  async function sendTest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTesting(true);
    setTestError("");
    try {
      const outcome = await api<MailTestResult>("/manage/mail/test", {
        method: "POST",
        ...jsonBody({ recipient, draft: draft() }),
      });
      setResult(outcome);
      if (outcome.ok) toast.success("测试邮件已交给邮件服务");
      else toast.error("测试发送失败，请查看原因");
    } catch (requestError) {
      setTestError(formatApiError(requestError));
    } finally {
      setTesting(false);
    }
  }

  if (sessionLoading) return <AppShell title="邮件服务" eyebrow="ADMIN"><PageLoading /></AppShell>;
  if (!allowed) return <AppShell title="邮件服务" eyebrow="ADMIN"><PageError message="当前账户没有系统管理权限。" /></AppShell>;
  const lastTest = result ?? data?.last_test ?? null;
  return <AppShell title="邮件服务" eyebrow="ADMINISTRATION">
    <AdminTabs />
    <div className="ai-section-title">
      <div>
        <h2>注册与找回密码的发信通道</h2>
        <p>验证码邮件走 Resend 或自建 SMTP。密钥加密保存在服务器，本页只显示是否已保存。</p>
      </div>
      <StatusPill tone={data?.source === "none" ? "warm" : "live"}>{sourceLabels[data?.source ?? "none"]}</StatusPill>
    </div>
    {loading && !data ? <PageLoading /> : error ? <PageError message={error} retry={reload} /> : (
      <div className="ai-playground">
        <form className="ai-form-panel" onSubmit={save}>
          <div className="ai-section-title"><h3>通道设置</h3></div>
          <div className="ai-form-grid">
            <label className="form-field"><span>发信通道</span><select value={provider} onChange={(event) => setProvider(event.target.value as MailSettings["provider"])}><option value="resend">Resend（HTTPS API）</option><option value="smtp">SMTP 服务器</option></select></label>
            <label className="form-field"><span>发件人</span><input value={sender} onChange={(event) => setSender(event.target.value)} maxLength={200} required placeholder="UESTC AI <noreply@uestcai.top>" /></label>
            {provider === "resend" ? (
              <label className="form-field ai-wide"><span>Resend API Key</span><input type="password" value={resendSecret} onChange={(event) => setResendSecret(event.target.value)} autoComplete="new-password" spellCheck={false} placeholder={data?.resend.secret_saved ? "已保存，留空保持不变" : "re_…"} /></label>
            ) : <>
              <label className="form-field"><span>SMTP 服务器</span><input value={smtpHost} onChange={(event) => setSmtpHost(event.target.value)} maxLength={200} placeholder="smtpdm.aliyun.com" /></label>
              <label className="form-field"><span>端口</span><input type="number" min="1" max="65535" value={smtpPort} onChange={(event) => setSmtpPort(event.target.value)} /></label>
              <label className="form-field"><span>加密方式</span><select value={smtpSecurity} onChange={(event) => setSmtpSecurity(event.target.value as "ssl" | "starttls")}><option value="ssl">SSL（465）</option><option value="starttls">STARTTLS（587/80）</option></select></label>
              <label className="form-field"><span>用户名</span><input value={smtpUsername} onChange={(event) => setSmtpUsername(event.target.value)} maxLength={200} placeholder="通常是发信地址" /></label>
              <label className="form-field ai-wide"><span>SMTP 密码</span><input type="password" value={smtpSecret} onChange={(event) => setSmtpSecret(event.target.value)} autoComplete="new-password" spellCheck={false} placeholder={data?.smtp.secret_saved ? "已保存，留空保持不变" : "填写控制台生成的 SMTP 密码"} /></label>
            </>}
            <label className="form-field ai-wide"><span>失败自动切换</span><input type="checkbox" checked={fallback} onChange={(event) => setFallback(event.target.checked)} /><small>开启后，主通道发送失败会用另一个通道再试一次。</small></label>
          </div>
          <FieldError>{formError}</FieldError>
          <div className="ai-button-row">
            <button className="primary-button" disabled={saving}><Mail size={14} />{saving ? "正在保存" : "保存设置"}</button>
            <button className="outline-button" type="button" onClick={() => void reload()} disabled={loading}>重新读取</button>
          </div>
        </form>
        <section className="ai-response" aria-live="polite">
          <span className="eyebrow"><i />TEST DELIVERY</span>
          <form className="ai-form-panel" onSubmit={sendTest}>
            <label className="form-field"><span>测试收件人</span><input type="email" value={recipient} onChange={(event) => setRecipient(event.target.value)} required placeholder="填写一个你能查看的邮箱" /></label>
            <FieldError>{testError}</FieldError>
            <div className="ai-button-row"><button className="primary-button" disabled={testing || !sender}><Send size={14} />{testing ? "正在发送" : "发送测试邮件"}</button></div>
            <small>测试使用上面表单里的值，不必先保存；测试不会改变已保存的配置。</small>
          </form>
          {lastTest && <div className={`inline-alert ${lastTest.ok ? "success" : "error"}`} role="status">
            <strong>{lastTest.ok ? `已通过 ${lastTest.provider === "smtp" ? "SMTP" : "Resend"} 发送` : "发送失败"}</strong>
            <span> · {lastTest.recipient} · {lastTest.elapsed_ms} ms{lastTest.fallback_used ? " · 已自动切换通道" : ""}{lastTest.at ? ` · ${formatBeijing(lastTest.at, { dateStyle: "medium", timeStyle: "short" })}` : ""}</span>
            {!lastTest.ok && <p>{describeReason(lastTest.reason)}{lastTest.detail ? `（${lastTest.detail}）` : ""}</p>}
          </div>}
        </section>
      </div>)}
  </AppShell>;
}

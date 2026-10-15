"use client";

import { PrefetchLink as Link } from "@/app/components/PrefetchLink";
import { UserLink } from "@/app/components/UserLink";
import { FormEvent, useCallback, useMemo, useState } from "react";
import { ArrowRight, ClipboardCheck, Copy, LogIn, LogOut, Plus, ShieldCheck, TicketCheck, Trash2, UserMinus, Users } from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { ConfirmDialog } from "@/app/components/ConfirmDialog";
import { useSession } from "@/app/components/SessionProvider";
import { useToast } from "@/app/components/ToastProvider";
import { EmptyState, FieldError, PageLoading, StatusPill } from "@/app/components/ui";
import { api, formatApiError, jsonBody } from "@/app/lib/api";
import { copyText } from "@/app/lib/clipboard";
import type { Competition, Registration, Submission, Team, User } from "@/app/lib/domain";
import { validateForm } from "@/app/lib/formValidation";
import { ruleSummary } from "@/app/lib/teamRules";
import { useApiResource } from "@/app/lib/useApiResource";

export default function DashboardPage() {
  const { user, loading: sessionLoading } = useSession();
  const toast = useToast();
  const teamResource = useApiResource<Team[]>(user ? "/me/teams" : null);
  const registrationResource = useApiResource<Registration[]>(user ? "/me/registrations" : null);
  const submissionResource = useApiResource<Submission[]>(user ? "/me/submissions" : null);
  const competitionResource = useApiResource<Competition[]>(user ? "/competitions?status=published" : null);
  const teams = teamResource.data ?? [];
  const registrations = useMemo(() => registrationResource.data ?? [], [registrationResource.data]);
  const submissions = submissionResource.data ?? [];
  const competitions = competitionResource.data ?? [];
  const [error, setError] = useState("");
  const [teamName, setTeamName] = useState("");
  const [competitionId, setCompetitionId] = useState("");
  const selectedCompetitionId = competitionId || competitionResource.data?.[0]?.id || "";
  const competitionTeam = teams.find((team) => team.competition_id === selectedCompetitionId) ?? null;
  const competitionRules = ruleSummary(competitions.find((item) => item.id === selectedCompetitionId)?.config);
  const rulesExempt = ["admin", "organizer", "editor", "reviewer"].includes(user?.role ?? "");
  const [inviteCode, setInviteCode] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<null | { kind: "team" | "registration" | "submission"; id: string; title: string }>(null);
  const [deleteError, setDeleteError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [memberError, setMemberError] = useState("");
  const [memberBusy, setMemberBusy] = useState("");

  const { reload: reloadTeams } = teamResource;
  const { reload: reloadRegistrations } = registrationResource;
  const { reload: reloadSubmissions } = submissionResource;
  const { reload: reloadCompetitions } = competitionResource;
  const load = useCallback(() => Promise.all([reloadTeams(), reloadRegistrations(), reloadSubmissions(), reloadCompetitions()]),
    [reloadTeams, reloadRegistrations, reloadSubmissions, reloadCompetitions]);

  const registrationsByTeam = useMemo(() => registrations.reduce<Record<string, Registration[]>>((result, item) => {
    (result[item.team_id] ??= []).push(item); return result;
  }, {}), [registrations]);

  async function createTeam(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    const validationError = validateForm(event.currentTarget);
    if (validationError) return;
    try {
      await api("/teams", { method: "POST", ...jsonBody({ competition_id: selectedCompetitionId, name: teamName }) });
      setTeamName(""); await load(); toast.success("队伍已创建，邀请码可发给队友");
    } catch (requestError) { setError(formatApiError(requestError)); }
  }

  async function joinTeam(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    const validationError = validateForm(event.currentTarget);
    if (validationError) return;
    try {
      await api("/teams/join", { method: "POST", ...jsonBody({ invite_code: inviteCode }) });
      setInviteCode(""); await load(); toast.success("已加入队伍");
    } catch (requestError) { setError(formatApiError(requestError)); }
  }

  async function remove() {
    if (!deleteTarget) return;
    setDeleting(true); setDeleteError("");
    const endpoint = deleteTarget.kind === "team" ? `/teams/${deleteTarget.id}` : deleteTarget.kind === "registration" ? `/registrations/${deleteTarget.id}` : `/submissions/${deleteTarget.id}`;
    try {
      await api(endpoint, { method: "DELETE" });
      const successMessage = deleteTarget.kind === "team" ? "队伍已删除" : deleteTarget.kind === "registration" ? "报名已取消" : "草稿作品已删除";
      setDeleteTarget(null); await load(); toast.success(successMessage);
    } catch (requestError) { setDeleteError(formatApiError(requestError)); }
    finally { setDeleting(false); }
  }


  async function removeMember(team: Team, member: User) {
    if (memberBusy) return;
    setMemberError("");
    setMemberBusy(`remove:${team.id}:${member.id}`);
    try {
      await api(`/teams/${team.id}/members/${member.id}`, { method: "DELETE" });
      await load();
      toast.success(`已将 ${member.name} 移出队伍`);
    } catch (requestError) { setMemberError(formatApiError(requestError)); }
    finally { setMemberBusy(""); }
  }

  async function makeCaptain(team: Team, member: User) {
    if (memberBusy) return;
    setMemberError("");
    setMemberBusy(`captain:${team.id}:${member.id}`);
    try {
      await api(`/teams/${team.id}/captain`, { method: "POST", ...jsonBody({ user_id: member.id }) });
      await load();
      toast.success(`已将队长转让给 ${member.name}`);
    } catch (requestError) { setMemberError(formatApiError(requestError)); }
    finally { setMemberBusy(""); }
  }

  async function leaveTeam(team: Team) {
    if (memberBusy) return;
    setMemberError("");
    setMemberBusy(`leave:${team.id}`);
    try {
      await api(`/teams/${team.id}/leave`, { method: "POST" });
      await load();
      toast.success(`已退出 ${team.name}`);
    } catch (requestError) { setMemberError(formatApiError(requestError)); }
    finally { setMemberBusy(""); }
  }

  async function copyInviteCode(inviteCode: string) {
    try {
      await copyText(inviteCode);
      toast.success(`邀请码 ${inviteCode} 已复制`);
    } catch {
      toast.error("邀请码复制失败，请手动选择后复制");
    }
  }

  if (sessionLoading) return <AppShell title="工作台" eyebrow="DASHBOARD"><PageLoading label="正在确认账户" /></AppShell>;
  if (!user) return <AppShell title="工作台" eyebrow="DASHBOARD"><div className="sign-in-required"><LogIn size={22} /><h2>登录后管理参赛工作</h2><p>队伍、报名和提交记录只对账户本人可见。</p><Link className="primary-button" href="/login?next=/dashboard">登录或注册 <ArrowRight size={16} /></Link></div></AppShell>;

  return (
    <AppShell title={`${user.name}的工作台`} eyebrow="DASHBOARD" actions={<Link className="primary-button compact-button" href="/problems"><Plus size={15} />选择题目</Link>}>
      <div className="page-intro"><p>管理队伍、报名与作品。</p><Link className="outline-button" href={`/people/${user.id}`}>个人主页 · 修改密码 <ArrowRight size={15} /></Link></div>
      <>
        {error && <div className="inline-alert error">{error}</div>}
        <section className="dashboard-section">
          <header className="section-header"><div><span className="eyebrow"><i />TEAMS</span><h2>我的队伍</h2></div><span className="section-note">邀请码用于邀请成员，不要公开发布</span></header>
          {teamResource.loading || registrationResource.loading ? <PageLoading label="正在读取队伍" /> : teamResource.error || registrationResource.error ? <div role="alert">{teamResource.error || registrationResource.error}<button type="button" onClick={() => void load()}>重试</button></div> : teams.length ? <div className="team-list">{teams.map((team) => {
            const isCaptain = team.captain_id === user.id;
            const members = team.members ?? [];
            return <div className="team-entry" key={team.id}>
              <div className="team-row">
                <div className="team-symbol"><Users size={18} /></div>
                <div className="team-main"><strong>{team.name}</strong><span>{isCaptain ? "你是队长" : "你是队员"} · 共 {members.length} 人</span></div>
                <button type="button" className="invite-code" title="复制邀请码" onClick={() => void copyInviteCode(team.invite_code)}><Copy size={13} />{team.invite_code}</button>
                <div className="team-registrations">{(registrationsByTeam[team.id] ?? []).map((registration) => <span className="registration-chip" key={registration.id}><StatusPill tone="live">{registration.track_name}</StatusPill><button type="button" title={`取消 ${registration.track_name} 报名`} aria-label={`取消 ${registration.track_name} 报名`} onClick={() => setDeleteTarget({ kind: "registration", id: registration.id, title: `${team.name} / ${registration.track_name}` })}><Trash2 size={12} /></button></span>)}{!registrationsByTeam[team.id]?.length && <StatusPill tone="muted">尚未报名</StatusPill>}</div>
                {isCaptain
                  ? <button type="button" className="icon-button team-delete" title="解散队伍" aria-label={`解散队伍 ${team.name}`} onClick={() => setDeleteTarget({ kind: "team", id: team.id, title: team.name })}><Trash2 size={15} /></button>
                  : <button type="button" className="icon-button team-leave" title="退出队伍" aria-label={`退出队伍 ${team.name}`} disabled={memberBusy === `leave:${team.id}`} onClick={() => void leaveTeam(team)}><LogOut size={15} /></button>}
              </div>
              <div className="team-members">
                <div className="team-member-list">
                  {members.map((member) => <span className="team-member" key={member.id}>
                    <UserLink id={member.id} name={member.name} />
                    {member.id === team.captain_id && <em className="team-captain">队长</em>}
                    {isCaptain && member.id !== user.id && <span className="team-member-actions">
                      <button type="button" title={`将队长转让给 ${member.name}`} aria-label={`将队长转让给 ${member.name}`} disabled={memberBusy === `captain:${team.id}:${member.id}`} onClick={() => void makeCaptain(team, member)}><ShieldCheck size={13} /></button>
                      <button type="button" title={`将 ${member.name} 移出队伍`} aria-label={`将 ${member.name} 移出队伍`} disabled={memberBusy === `remove:${team.id}:${member.id}`} onClick={() => void removeMember(team, member)}><UserMinus size={13} /></button>
                    </span>}
                  </span>)}
                </div>
              </div>
            </div>;
          })}</div> : <EmptyState title="还没有队伍" description="可以创建自己的队伍，或使用邀请码加入。" />}
          <div className="team-actions-grid">
            <form className="form-panel compact-form" onSubmit={createTeam} noValidate><h3>创建队伍</h3><label className="form-field"><span>赛事</span><select value={selectedCompetitionId} onChange={(event) => setCompetitionId(event.target.value)} required>{competitions.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label><label className="form-field"><span>队伍名称</span><input value={teamName} onChange={(event) => setTeamName(event.target.value)} required /></label><button className="outline-button" disabled={!selectedCompetitionId || (Boolean(competitionTeam) && !rulesExempt)}><Plus size={15} />创建</button>{competitionRules && <p>本场规则：{competitionRules}{rulesExempt && "（评委与管理员不受此限制）"}。</p>}{competitionTeam && !rulesExempt && <p>你在这场比赛里已经有队伍「{competitionTeam.name}」。每场比赛每人只能加入一支队伍，想换队请先退出原队伍。</p>}</form>
            <form className="form-panel compact-form" onSubmit={joinTeam} noValidate><h3>加入队伍</h3><label className="form-field"><span>8 位邀请码</span><input value={inviteCode} onChange={(event) => setInviteCode(event.target.value.toUpperCase())} minLength={8} maxLength={8} required /></label><p>加入后即可和队友共享报名与作品记录。每场比赛每人只能加入一支队伍，已在本场比赛中时无法再加入另一支。</p><button className="outline-button"><TicketCheck size={15} />加入</button></form>
          </div>
          <FieldError>{error || competitionResource.error}</FieldError>
          {memberError && <div className="inline-alert error" role="alert">{memberError}</div>}
        </section>
        <section className="dashboard-section">
          <header className="section-header"><div><span className="eyebrow"><i />SUBMISSIONS</span><h2>我的作品</h2></div><Link href="/problems">从题库新建提交 <ArrowRight size={15} /></Link></header>
          {submissionResource.loading ? <PageLoading label="正在读取作品" /> : submissionResource.error ? <div role="alert">{submissionResource.error}<button type="button" onClick={() => void reloadSubmissions()}>重试</button></div> : !submissions.length ? <EmptyState title="还没有作品" description="进入具体题目后创建第一份 README 提交。" /> : <div className="submission-list">{submissions.map((submission) => { const isDraft = submission.status === "draft"; return <div key={submission.id}><Link href={isDraft ? `/submit/${submission.problem_slug}?submission=${submission.id}` : `/works/${submission.id}`}>
            <ClipboardCheck size={18} /><div><strong>{submission.title}</strong><span>{submission.problem_code} · {submission.team_name}</span></div><StatusPill tone={isDraft ? "warm" : "live"}>{isDraft ? "草稿" : "已正式提交"}</StatusPill><ArrowRight size={16} />
          </Link>{submission.status === "draft" && <button type="button" className="icon-button submission-delete" title="删除草稿作品" aria-label={`删除草稿作品 ${submission.title}`} onClick={() => setDeleteTarget({ kind: "submission", id: submission.id, title: submission.title })}><Trash2 size={15} /></button>}</div>; })}</div>}
        </section>
      </>
      <ConfirmDialog open={Boolean(deleteTarget)} title={`删除“${deleteTarget?.title ?? ""}”？`} description={deleteTarget?.kind === "team" ? "只有没有报名和作品记录的队伍可以删除。队员关系与邀请码会同时失效。" : deleteTarget?.kind === "registration" ? "只有尚未产生作品的报名可以取消，之后仍可重新报名。" : "只有未送审、未计分的草稿作品可以删除，草稿版本和附件会一并移除。"} busy={deleting} error={deleteError} onCancel={() => { setDeleteTarget(null); setDeleteError(""); }} onConfirm={() => void remove()} />
    </AppShell>
  );
}


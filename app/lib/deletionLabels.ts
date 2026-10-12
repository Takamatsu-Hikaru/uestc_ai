import type { ImpactItem } from "@/app/components/TypedDeleteDialog";

const competitionLabels: Record<string, string> = {
  tracks: "赛道", problems: "赛题", teams: "队伍", team_members: "队伍成员", registrations: "报名",
  submissions: "作品", submission_versions: "作品版本", submission_assets: "作品附件", uploaded_files: "上传文件",
  reviews: "评审", score_batches: "成绩批次", scores: "评分", evaluation_runs: "测评记录",
  evaluation_artifacts: "测评证据", checkpoint_entries: "进度记录", competition_reviewers: "评委分配",
  ai_grants: "AI 授权", ai_keys: "AI 密钥", ai_usage_records: "AI 用量记录",
  compute_grants: "算力授权", compute_instances: "算力实例", compute_sessions: "算力会话",
  manual_compute_accounts: "手动发放的算力账号（保留）",
};

const userLabels: Record<string, string> = {
  sessions: "登录会话（将被注销）", team_memberships: "队伍成员身份", teams_deleted: "将被一并删除的队伍",
  teams_captain_transferred: "将转让队长的队伍", teams_member_removed: "将被移出的队伍",
  submissions_deleted: "随队伍删除的作品", submission_versions_authored: "撰写的作品版本",
  submission_versions_reassigned: "改派给队长的作品版本", reviews: "评审记录",
  submitted_reviews_in_locked_competitions: "已锁定赛事中的已提交评审", competition_reviewer_assignments: "评委分配",
  score_batches_imported: "导入的成绩批次（置空）", ai_keys_created: "创建的 AI 密钥", ai_keys_disabled: "将被停用的 AI 密钥",
  compute_sessions_requested: "发起的算力会话", compute_resources_deleted: "随队伍删除的算力记录",
  contents_authored: "发布的内容（保留，作者置空）", markdown_assets_reassigned: "上传的 Markdown 资源（转交管理员）",
  invites_created: "创建的邀请码（转交管理员）", invites_used: "使用的邀请码", staged_assets: "暂存附件",
  uploaded_files: "将被删除的上传文件", audit_rows_referencing_user: "审计记录（保留）",
};

function toItems(counts: Record<string, number>, labels: Record<string, string>): ImpactItem[] {
  return Object.entries(labels)
    .filter(([key]) => key in counts)
    .map(([key, label]) => ({ label, count: counts[key] ?? 0 }));
}

export const competitionImpactItems = (counts: Record<string, number>) => toItems(counts, competitionLabels);
export const userImpactItems = (counts: Record<string, number>) => toItems(counts, userLabels);

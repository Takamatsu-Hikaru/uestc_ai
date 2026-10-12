"""Administrators issue accounts; only admins and the owning team reveal them."""
from flask import Blueprint, jsonify

from ..ai_gateway import GatewayError, decrypt_keys, encrypt_keys
from ..ai_quotas import lock_competition, lock_problem
from ..compute_accounts import account_metadata, delivery_mode
from ..compute_models import ComputeAccount, ComputePolicy
from ..extensions import db
from ..models import Problem, Team
from ..security import current_user, require_user, team_member
from ..utils import audit
from .ai import data_object

compute_accounts_bp = Blueprint("compute_accounts", __name__)


@compute_accounts_bp.errorhandler(GatewayError)
def account_error(error):
    db.session.rollback()
    return jsonify({"error": str(error), "code": error.code}), error.status


def manual_problem(problem_id):
    problem = db.session.get(Problem, problem_id)
    if not problem:
        raise GatewayError("题目不存在。", 404)
    policy = db.session.get(ComputePolicy, problem_id, populate_existing=True)
    if not policy or delivery_mode(policy.config) != "manual_account":
        raise GatewayError("请先保存本题的手动账号发放方式。", 409)
    return problem, policy


def no_store(data):
    response = jsonify(data)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@compute_accounts_bp.get("/compute/manage/problems/<problem_id>/accounts")
@require_user("admin", "organizer")
def accounts(problem_id):
    problem, policy = manual_problem(problem_id)
    existing = {a.team_id: a for a in ComputeAccount.query.filter_by(problem_id=problem_id).all()}
    teams = Team.query.filter_by(competition_id=problem.track.competition_id).order_by(Team.name, Team.id).all()
    return no_store([account_metadata(t, problem, policy, existing.get(t.id)) for t in teams])


@compute_accounts_bp.put("/compute/manage/problems/<problem_id>/accounts/<team_id>")
@require_user("admin")
def save_account(problem_id, team_id):
    problem, _ = manual_problem(problem_id)
    lock_competition(problem.track.competition_id)
    lock_problem(problem_id)
    problem, policy = manual_problem(problem_id)
    team = db.session.get(Team, team_id)
    if not team or team.competition_id != problem.track.competition_id:
        raise GatewayError("队伍不属于本题赛事。", 400)
    data = data_object()
    if set(data) - {"username", "password", "notes", "enabled"}:
        raise GatewayError("账号配置字段无效。")
    username, password, notes = (data.get(k, "") for k in ("username", "password", "notes"))
    enabled = data.get("enabled", True)
    if (not isinstance(username, str) or not 1 <= len(username.strip()) <= 200
            or any(ord(c) < 32 for c in username) or not isinstance(password, str)
            or len(password) > 512 or any(ord(c) < 32 for c in password)
            or not isinstance(notes, str) or len(notes) > 4000 or type(enabled) is not bool):
        raise GatewayError("请填写有效账号和密码，备注最多 4000 个字符。")
    account = ComputeAccount.query.filter_by(problem_id=problem_id, team_id=team_id).first()
    if not password:
        if not account:
            raise GatewayError("首次发放必须填写密码。")
        password = decrypt_keys(account.secret)[1]
    account = account or ComputeAccount(problem_id=problem_id, team_id=team_id)
    account.secret = encrypt_keys([username.strip(), password, notes.strip()])
    account.enabled = enabled
    db.session.add(account)
    audit("compute.account.saved", "problem", problem_id, {"team_id": team_id, "enabled": enabled})
    db.session.commit()
    return no_store(account_metadata(team, problem, policy, account))


@compute_accounts_bp.patch("/compute/manage/problems/<problem_id>/accounts/<team_id>")
@require_user("admin")
def pause_account(problem_id, team_id):
    problem, _ = manual_problem(problem_id)
    lock_competition(problem.track.competition_id)
    lock_problem(problem_id)
    manual_problem(problem_id)
    account = ComputeAccount.query.filter_by(problem_id=problem_id, team_id=team_id).first()
    if not account:
        raise GatewayError("尚未发放账号。", 404)
    data = data_object()
    if set(data) != {"enabled"} or type(data["enabled"]) is not bool:
        raise GatewayError("仅接受账号启用状态。")
    account.enabled = data["enabled"]
    audit("compute.account.status", "problem", problem_id, {"team_id": team_id, "enabled": account.enabled})
    db.session.commit()
    return no_store({"ok": True})


@compute_accounts_bp.post("/compute/accounts/<account_id>/credentials")
@require_user()
def credentials(account_id):
    account = db.session.get(ComputeAccount, account_id)
    user = current_user()
    if not account or user.role == "reviewer" or (user.role != "admin" and not team_member(account.team_id, user.id)):
        raise GatewayError("仅本队成员与管理员可查看账号。", 403, "forbidden")
    _, policy = manual_problem(account.problem_id)
    if not policy.config["enabled"] or not account.enabled:
        raise GatewayError("本题账号发放已暂停。", 403)
    username, password, notes = decrypt_keys(account.secret)
    audit("compute.account.viewed", "problem", account.problem_id, {"team_id": account.team_id})
    db.session.commit()
    return no_store({"username": username, "password": password, "notes": notes,
                     "login_url": policy.config["login_url"]})

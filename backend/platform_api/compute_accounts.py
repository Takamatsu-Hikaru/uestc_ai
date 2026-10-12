"""Private manual account delivery, separate from managed instances and judges."""
from urllib.parse import urlsplit

from sqlalchemy import and_

from .ai_gateway import GatewayError
from .compute_models import ComputeAccount, ComputePolicy
from .extensions import db
from .models import Problem, Team, TeamMember, Track, iso

ACCOUNT_LOGIN_URL = "https://www.autodl.com/login"


def delivery_mode(config):
    return config.get("mode", "managed") if isinstance(config, dict) else "managed"


def manual_policy_values(data):
    if set(data) - {"mode", "enabled", "login_url", "instructions"}:
        raise GatewayError("手动账号方式不接受实例渠道、卡时或费用计量配置。")
    enabled = data.get("enabled", True)
    login_url = data.get("login_url", ACCOUNT_LOGIN_URL)
    instructions = data.get("instructions", "")
    if type(enabled) is not bool:
        raise GatewayError("enabled 必须是布尔值。")
    if not isinstance(login_url, str) or len(login_url) > 300:
        raise GatewayError("AutoDL 登录地址无效。")
    try:
        url = urlsplit(login_url)
        if (url.scheme != "https" or url.hostname not in {"autodl.com", "www.autodl.com"}
                or url.username or url.password or url.port not in {None, 443}
                or url.query or url.fragment or any(ord(c) < 32 for c in login_url)):
            raise ValueError()
    except ValueError:
        raise GatewayError("登录地址须为不含凭据的 AutoDL 官方 HTTPS 地址。") from None
    if not isinstance(instructions, str) or len(instructions) > 4000:
        raise GatewayError("账号使用说明不能超过 4000 个字符。")
    return {"mode": "manual_account", "enabled": enabled, "login_url": login_url,
            "instructions": instructions.strip()}


def account_metadata(team, problem, policy, account):
    enabled = bool(policy.config["enabled"] and (not account or account.enabled))
    return {"id": account.id if account else None, "team_id": team.id, "team_name": team.name,
            "problem_id": problem.id, "problem_title": problem.title,
            "competition_name": team.competition.name, "enabled": enabled,
            "account_enabled": bool(account and account.enabled),
            "status": "paused" if not enabled else "issued" if account else "pending",
            "login_url": policy.config["login_url"], "instructions": policy.config["instructions"],
            "updated_at": iso(account.updated_at) if account else None}


def manual_overview(user):
    if user.role == "reviewer":
        return []
    query = (db.session.query(Team, Problem, ComputePolicy, ComputeAccount)
             .join(Track, Track.competition_id == Team.competition_id)
             .join(Problem, Problem.track_id == Track.id)
             .join(ComputePolicy, ComputePolicy.problem_id == Problem.id)
             .outerjoin(ComputeAccount, and_(ComputeAccount.team_id == Team.id,
                                            ComputeAccount.problem_id == Problem.id)))
    if user.role not in {"admin", "organizer"}:
        query = query.join(TeamMember, TeamMember.team_id == Team.id).filter(TeamMember.user_id == user.id)
    return [account_metadata(team, problem, policy, account)
            for team, problem, policy, account in query.order_by(Problem.id, Team.id).all()
            if delivery_mode(policy.config) == "manual_account"]

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import event, text
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_backend_api as fixtures  # noqa: E402
from platform_api.ai_models import AIGrant, AIKey, AIUsage  # noqa: E402
from platform_api.compute_models import ComputeGrant, ComputeInstance, ComputeProvider, ComputeSession  # noqa: E402
from platform_api.extensions import db  # noqa: E402
from platform_api.judge_models import JudgePool  # noqa: E402
from platform_api.models import (  # noqa: E402
    AuditLog, Competition, CompetitionReviewer, Content, EvaluationRun, MarkdownAsset, Problem,
    Registration, RegistrationInvite, Review, Score, ScoreBatch, Session, StagedSubmissionAsset,
    Submission, SubmissionAsset, SubmissionVersion, Team, TeamMember, Track, User,
)
from platform_api.progress_models import CheckpointEntry, EvaluationArtifact  # noqa: E402

ADMIN = "admin@uestcai.top"


def utc_in(days=1):
    return datetime.now(timezone.utc) + timedelta(days=days)


class AdminDeletionTests(unittest.TestCase):
    login = fixtures.PlatformApiTestCase.login

    def setUp(self):
        fixtures.PlatformApiTestCase.setUp(self)
        with self.app.app_context():
            event.listen(db.engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
            db.engine.dispose()
        self.uploads = Path(self.app.config["UPLOAD_FOLDER"])
        self.uploads.mkdir(parents=True, exist_ok=True)
        self.login(self.admin, ADMIN)

    def tearDown(self):
        with self.app.app_context():
            self.assertEqual(db.session.execute(text("PRAGMA foreign_key_check")).all(), [])
        fixtures.PlatformApiTestCase.tearDown(self)

    # ------------------------------------------------------------ builders
    def file(self, name):
        (self.uploads / name).write_bytes(b"x")
        return name

    def user(self, email, role="member", name=None):
        user = User(email=email, name=name or email.split("@")[0], password_hash=generate_password_hash("pw-123456"), role=role)
        db.session.add(user)
        db.session.flush()
        return user

    def client_for(self, email):
        client = self.app.test_client()
        self.login(client, email, "pw-123456")
        return client

    def competition(self, slug="doomed"):
        comp = Competition(slug=slug, name="Doomed", summary="s", status="published")
        db.session.add(comp)
        db.session.flush()
        track = Track(competition_id=comp.id, slug="t", name="T")
        db.session.add(track)
        db.session.flush()
        problem = Problem(track_id=track.id, code="P1", slug="p1", title="P1")
        db.session.add(problem)
        db.session.flush()
        return comp, track, problem

    def team_with_work(self, comp, track, problem, captain, members=(), suffix="a", files=True, scored=True):
        """One team with a submission and every kind of dependent row."""
        team = Team(competition_id=comp.id, name=f"Team {suffix}", invite_code=f"INV{suffix}".upper().ljust(8, "0")[:8], captain_id=captain.id)
        db.session.add(team)
        db.session.flush()
        for member in (captain, *members):
            db.session.add(TeamMember(team_id=team.id, user_id=member.id))
        db.session.add(Registration(competition_id=comp.id, track_id=track.id, team_id=team.id))
        sub = Submission(problem_id=problem.id, team_id=team.id, title="S", status="submitted", current_version=1)
        db.session.add(sub)
        db.session.flush()
        version = SubmissionVersion(submission_id=sub.id, version=1, readme_md="r", status="submitted", created_by=captain.id)
        db.session.add(version)
        db.session.flush()
        names = {k: f"{k}-{suffix}.bin" for k in ("asset", "artifact", "package", "ckpt")}
        if files:
            for name in names.values():
                self.file(name)
        db.session.add(SubmissionAsset(submission_version_id=version.id, original_name="a", storage_name=names["asset"], content_type="x", size=1))
        reviewer = User.query.filter_by(role="reviewer").first()
        db.session.add(Review(submission_version_id=version.id, reviewer_id=reviewer.id, status="submitted", total_score=1))
        batch = ScoreBatch(competition_id=comp.id, problem_id=problem.id, source="s", label="l", imported_by=User.query.filter_by(email=ADMIN).one().id)
        db.session.add(batch)
        db.session.flush()
        if scored:
            db.session.add(Score(batch_id=batch.id, submission_version_id=version.id, total_score=1))
        run = EvaluationRun(problem_id=problem.id, submission_version_id=version.id, config_snapshot={"adapter": "x"},
                            submission_snapshot={}, status="completed", package_storage_name=names["package"])
        db.session.add(run)
        db.session.flush()
        db.session.add(EvaluationArtifact(run_id=run.id, name="n", storage_name=names["artifact"], size=1))
        db.session.add(CheckpointEntry(problem_id=problem.id, team_id=team.id, checkpoint_id="c1", content_md="c",
                                       evaluation_run_id=run.id, package_storage_name=names["ckpt"]))
        grant = AIGrant(team_id=team.id, problem_id=problem.id, allowed_models=[], max_calls=1, max_tokens=1)
        db.session.add(grant)
        db.session.flush()
        key = AIKey(grant_id=grant.id, created_by=captain.id, name="k", key_hash=f"hash-{suffix}", prefix="p")
        db.session.add(key)
        db.session.flush()
        db.session.add(AIUsage(grant_id=grant.id, key_id=key.id, evaluation_run_id=run.id, model="m", endpoint="e",
                               deadline=utc_in(), charged_tokens=1, charged_cost_micros=1))
        provider = ComputeProvider.query.first() or ComputeProvider(
            name="prov", secret="s", image_uuid="i", gpu_spec_uuid="g", gpu_label="l", hourly_price_millis=1)
        db.session.add(provider)
        db.session.flush()
        cgrant = ComputeGrant(team_id=team.id, problem_id=problem.id, provider_id=provider.id, max_gpu_seconds=10)
        db.session.add(cgrant)
        db.session.flush()
        instance = ComputeInstance(grant_id=cgrant.id, provider_id=provider.id, name="i", remote_id=None)
        db.session.add(instance)
        db.session.flush()
        session = ComputeSession(grant_id=cgrant.id, instance_id=instance.id, request_id="r", requested_by=captain.id,
                                 state="finished", duration_seconds=1, gpu_count=1, rate_millis=1,
                                 reserved_gpu_seconds=1, reserved_cost_millis=1, next_check_at=utc_in())
        db.session.add(session)
        db.session.flush()
        ref = lambda item: SimpleNamespace(id=item.id)  # noqa: E731  (ids stay readable after the session closes)
        return SimpleNamespace(team=ref(team), submission=ref(sub), version=ref(version), run=ref(run), grant=ref(grant),
                               key=ref(key), cgrant=ref(cgrant), instance=ref(instance), session=ref(session),
                               batch=ref(batch), names=names)

    def build_competition(self):
        with self.app.app_context():
            comp, track, problem = self.competition()
            captain, other = self.user("cap@x.test"), self.user("mem@x.test")
            work = self.team_with_work(comp, track, problem, captain, (other,))
            db.session.add(CompetitionReviewer(competition_id=comp.id, reviewer_id=User.query.filter_by(role="reviewer").first().id))
            db.session.commit()
            return SimpleNamespace(id=comp.id, track=track.id, problem=problem.id, work=work, captain=captain.id,
                                   rows=[(Competition, comp.id), (Track, track.id), (Problem, problem.id), (Team, work.team.id),
                                         (Submission, work.submission.id), (SubmissionVersion, work.version.id),
                                         (EvaluationRun, work.run.id), (AIGrant, work.grant.id), (AIKey, work.key.id),
                                         (ComputeGrant, work.cgrant.id), (ComputeInstance, work.instance.id),
                                         (ComputeSession, work.session.id), (ScoreBatch, work.batch.id)])

    def delete_competition(self, client, comp_id, confirm="doomed", **kwargs):
        body = {} if confirm is None else {"confirm": confirm}
        return client.delete(f"/api/manage/competitions/{comp_id}", json=body, **kwargs)

    def exists(self, model, id_):
        with self.app.app_context():
            return db.session.get(model, id_) is not None

    # ------------------------------------------------------------ competition
    def test_delete_competition_with_submissions_removes_rows_files_and_keeps_audit(self):
        built = self.build_competition()
        with patch("platform_api.deletion.public_cache.invalidate_public_cache") as invalidate:
            response = self.delete_competition(self.admin, built.id)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(invalidate.called)
        for model, id_ in built.rows:
            self.assertFalse(self.exists(model, id_), model.__name__)
        for name in built.work.names.values():
            self.assertFalse((self.uploads / name).exists(), name)
        with self.app.app_context():
            for model in (Registration, Review, Score, EvaluationArtifact, CheckpointEntry, AIUsage, CompetitionReviewer):
                if model is Review:
                    self.assertEqual(model.query.filter_by(submission_version_id=built.work.version.id).count(), 0)
                elif model is Registration:
                    self.assertEqual(model.query.filter_by(competition_id=built.id).count(), 0)
                elif model is CompetitionReviewer:
                    self.assertEqual(model.query.filter_by(competition_id=built.id).count(), 0)
            audit = AuditLog.query.filter_by(action="competition.deleted", entity_id=built.id).one()
            self.assertEqual(audit.details["slug"], "doomed")
            self.assertEqual(audit.details["name"], "Doomed")
            self.assertEqual(audit.details["counts"]["submissions"], 1)
            self.assertEqual(audit.details["actor"]["email"], ADMIN)

    def test_confirmation_is_required_and_exact(self):
        built = self.build_competition()
        for confirm in (None, "", "Doomed", "doomed ", "other", 123, ["doomed"]):
            response = self.delete_competition(self.admin, built.id, confirm=confirm if confirm is not None else None)
            self.assertEqual(response.status_code, 400, confirm)
            self.assertIn("confirmation", response.get_json()["error"])
        no_body = self.admin.delete(f"/api/manage/competitions/{built.id}")
        self.assertEqual(no_body.status_code, 400)
        self.assertTrue(self.exists(Competition, built.id))
        with self.app.app_context():
            empty, _, _ = self.competition("empty-one")
            db.session.commit()
            empty_id = empty.id
        self.assertEqual(self.delete_competition(self.admin, empty_id, confirm="nope").status_code, 400)
        self.assertEqual(self.delete_competition(self.admin, empty_id, confirm="empty-one").status_code, 204)
        header = self.admin.delete(f"/api/manage/competitions/{built.id}", headers={"X-Confirm": "doomed"})
        self.assertEqual(header.status_code, 204)

    def test_permissions(self):
        built = self.build_competition()
        with self.app.app_context():
            self.user("org@x.test", role="organizer")
            empty, _, _ = self.competition("empty-two")
            db.session.commit()
            empty_id = empty.id
        member = self.client_for("cap@x.test")
        self.assertEqual(self.delete_competition(member, built.id).status_code, 403)
        self.assertEqual(self.delete_competition(self.member, built.id).status_code, 401)
        organizer = self.client_for("org@x.test")
        self.assertEqual(self.delete_competition(organizer, built.id).status_code, 403)
        self.assertTrue(self.exists(Competition, built.id))
        self.assertEqual(self.delete_competition(organizer, empty_id, confirm="empty-two").status_code, 204)

    def test_blockers_keep_all_data(self):
        built = self.build_competition()
        with self.app.app_context():
            session = db.session.get(ComputeSession, built.work.session.id)
            session.state = "running"
            db.session.commit()
        self.assertEqual(self.delete_competition(self.admin, built.id).get_json()["error"], "active compute sessions exist")
        with self.app.app_context():
            db.session.get(ComputeSession, built.work.session.id).state = "finished"
            instance = db.session.get(ComputeInstance, built.work.instance.id)
            instance.remote_id, instance.provider_status = "remote-1", "running"
            db.session.commit()
        blocked = self.delete_competition(self.admin, built.id)
        self.assertEqual((blocked.status_code, blocked.get_json()["error"]), (409, "remote compute instances not stopped"))
        for model, id_ in built.rows:
            self.assertTrue(self.exists(model, id_))
        with self.app.app_context():
            db.session.get(ComputeInstance, built.work.instance.id).provider_status = "released"
            provider = ComputeProvider.query.first()
            db.session.add(JudgePool(problem_id=built.problem, provider_id=provider.id, remote_id="judge", image="i",
                                     worker_id="w", dataset_manifests={}))
            db.session.commit()
        pool = self.delete_competition(self.admin, built.id)
        self.assertEqual(pool.status_code, 409)
        self.assertTrue(self.exists(Competition, built.id))
        with self.app.app_context():
            JudgePool.query.delete()
            db.session.commit()
        self.assertEqual(self.delete_competition(self.admin, built.id).status_code, 204)

    def test_file_cleanup_is_safe(self):
        built = self.build_competition()
        outside = self.uploads.parent / "outside.txt"
        outside.write_text("keep")
        keep = self.file("markdown-shared.bin")
        with self.app.app_context():
            db.session.add(MarkdownAsset(uploaded_by=db.session.get(User, built.captain).id, original_name="m", storage_name=keep,
                                         content_type="x", size=1, kind="image"))
            artifact = EvaluationArtifact.query.filter_by(run_id=built.work.run.id).one()
            artifact.storage_name = "../outside.txt"
            run = db.session.get(EvaluationRun, built.work.run.id)
            run.package_storage_name = keep
            db.session.commit()
        (self.uploads / built.work.names["ckpt"]).unlink()  # missing files are tolerated
        self.assertEqual(self.delete_competition(self.admin, built.id).status_code, 204)
        self.assertTrue(outside.exists())
        self.assertTrue((self.uploads / keep).exists())
        self.assertFalse((self.uploads / built.work.names["asset"]).exists())

    def test_files_survive_when_commit_fails(self):
        built = self.build_competition()
        with patch("platform_api.deletion.audit", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.delete_competition(self.admin, built.id)
        for name in built.work.names.values():
            self.assertTrue((self.uploads / name).exists())
        self.assertTrue(self.exists(Competition, built.id))

    def test_sql_failure_returns_500_without_cache_or_file_changes(self):
        from sqlalchemy.exc import SQLAlchemyError
        built = self.build_competition()
        with patch("platform_api.deletion.audit", side_effect=SQLAlchemyError("fk")), \
                patch("platform_api.deletion.public_cache.invalidate_public_cache") as invalidate:
            response = self.delete_competition(self.admin, built.id)
        self.assertEqual((response.status_code, response.get_json()["error"]), (500, "deletion failed"))
        self.assertFalse(invalidate.called)
        self.assertTrue((self.uploads / built.work.names["asset"]).exists())
        self.assertEqual(self.delete_competition(self.admin, built.id).status_code, 204)

    def test_archive_still_works_and_preview_matches(self):
        built = self.build_competition()
        archived = self.admin.patch(f"/api/manage/competitions/{built.id}", json={"status": "archived"})
        self.assertEqual((archived.status_code, archived.get_json()["status"]), (200, "archived"))
        preview = self.admin.get(f"/api/manage/competitions/{built.id}/deletion-impact").get_json()
        self.assertEqual(preview["confirm_text"], "doomed")
        self.assertTrue(preview["can_delete"] and preview["has_participation"])
        counts = preview["counts"]
        expected = {"tracks": 1, "problems": 1, "teams": 1, "team_members": 2, "registrations": 1, "submissions": 1,
                    "submission_versions": 1, "uploaded_files": 4, "reviews": 1, "scores": 1, "evaluation_runs": 1,
                    "ai_grants": 1, "ai_keys": 1, "ai_usage_records": 1, "compute_grants": 1, "compute_sessions": 1}
        for key, value in expected.items():
            self.assertEqual(counts[key], value, key)
        self.assertEqual(self.member.get(f"/api/manage/competitions/{built.id}/deletion-impact").status_code, 401)

    # ------------------------------------------------------------------ users
    def build_users(self):
        with self.app.app_context():
            comp, track, problem = self.competition("users-comp")
            victim = self.user("Victim@X.test", name="Victim")
            friend = self.user("friend@x.test")
            solo_work = self.team_with_work(comp, track, problem, victim, suffix="solo", scored=False)
            problem2 = Problem(track_id=track.id, code="P2", slug="p2", title="P2")
            db.session.add(problem2)
            db.session.flush()
            shared = self.team_with_work(comp, track, problem2, victim, (friend,), suffix="shared", files=False)
            self.file("staged.bin")
            db.session.add(StagedSubmissionAsset(uploaded_by=victim.id, original_name="s", storage_name="staged.bin", content_type="x", size=1))
            admin = User.query.filter_by(email=ADMIN).one()
            db.session.add(RegistrationInvite(code_hash="h1", code_prefix="AAAA", created_by=victim.id, expires_at=utc_in()))
            db.session.add(RegistrationInvite(code_hash="h2", code_prefix="BBBB", created_by=admin.id, expires_at=utc_in(),
                                              used_by=victim.id, used_at=utc_in()))
            db.session.add(Content(kind="post", slug="victim-post", title="t", author_id=victim.id))
            db.session.add(MarkdownAsset(uploaded_by=victim.id, original_name="m", storage_name="markdown-v.bin", content_type="x", size=1, kind="image"))
            db.session.add(AuditLog(action="x.y", entity_type="t", entity_id="e", actor_id=victim.id, details={}))
            from platform_api.security import hash_token
            db.session.add(Session(token_hash=hash_token("tok-victim"), user_id=victim.id, expires_at=utc_in()))
            db.session.commit()
            return SimpleNamespace(victim=victim.id, friend=friend.id, solo=solo_work, shared=shared, comp=comp.id)

    def delete_user(self, client, user_id, confirm="victim@x.test"):
        return client.delete(f"/api/admin/users/{user_id}", json={} if confirm is None else {"confirm": confirm})

    def test_delete_user_with_history(self):
        built = self.build_users()
        preview = self.admin.get(f"/api/admin/users/{built.victim}/deletion-impact").get_json()
        counts = preview["counts"]
        self.assertTrue(preview["can_delete"])
        self.assertEqual(preview["confirm_text"], "Victim@X.test")
        for key, value in {"sessions": 1, "team_memberships": 2, "teams_deleted": 1, "teams_captain_transferred": 1,
                           "submissions_deleted": 1, "submission_versions_reassigned": 1, "ai_keys_disabled": 1,
                           "invites_created": 1, "invites_used": 1, "contents_authored": 1, "markdown_assets_reassigned": 1,
                           "staged_assets": 1, "audit_rows_referencing_user": 1, "score_batches_imported": 0}.items():
            self.assertEqual(counts[key], value, key)
        with patch("platform_api.deletion.public_cache.invalidate_public_cache") as invalidate:
            response = self.delete_user(self.admin, built.victim, confirm=" VICTIM@x.test ")
        self.assertEqual(response.status_code, 204)
        self.assertTrue(invalidate.called)
        with self.app.app_context():
            admin = User.query.filter_by(email=ADMIN).one()
            self.assertIsNone(db.session.get(User, built.victim))
            self.assertIsNone(db.session.get(Team, built.solo.team.id))
            self.assertIsNone(db.session.get(Submission, built.solo.submission.id))
            shared_team = db.session.get(Team, built.shared.team.id)
            self.assertEqual(shared_team.captain_id, built.friend)
            self.assertEqual([m.user_id for m in shared_team.members], [built.friend])
            self.assertEqual(db.session.get(SubmissionVersion, built.shared.version.id).created_by, built.friend)
            key = db.session.get(AIKey, built.shared.key.id)
            self.assertEqual((key.created_by, key.enabled), (built.friend, False))
            self.assertEqual(db.session.get(ComputeSession, built.shared.session.id).requested_by, built.friend)
            self.assertEqual(Session.query.filter_by(user_id=built.victim).count(), 0)
            self.assertEqual(StagedSubmissionAsset.query.count(), 0)
            self.assertEqual(Content.query.filter_by(slug="victim-post").one().author_id, None)
            self.assertEqual(MarkdownAsset.query.filter_by(storage_name="markdown-v.bin").one().uploaded_by, admin.id)
            self.assertEqual(RegistrationInvite.query.filter_by(code_hash="h1").one().created_by, admin.id)
            self.assertIsNone(RegistrationInvite.query.filter_by(code_hash="h2").one().used_by)
            self.assertEqual(Review.query.filter_by(reviewer_id=built.victim).count(), 0)
            row = AuditLog.query.filter_by(action="x.y").one()
            self.assertIsNone(row.actor_id)
            self.assertEqual(row.details["actor_snapshot"]["email"], "Victim@X.test")
            audit = AuditLog.query.filter_by(action="user.deleted", entity_id=built.victim).one()
            self.assertEqual(audit.details["email"], "Victim@X.test")
            self.assertEqual(audit.actor_id, admin.id)
        self.assertFalse((self.uploads / "staged.bin").exists())
        self.assertFalse((self.uploads / built.solo.names["asset"]).exists())
        self.assertTrue((self.uploads / built.solo.names["asset"]).parent.exists())

    def test_revoked_session_token_stops_working(self):
        with self.app.app_context():
            self.user("gone@x.test")
            db.session.commit()
        victim = self.client_for("gone@x.test")
        self.assertEqual(victim.get("/api/auth/me").status_code, 200)
        with self.app.app_context():
            user_id = User.query.filter_by(email="gone@x.test").one().id
        self.assertEqual(self.delete_user(self.admin, user_id, confirm="gone@x.test").status_code, 204)
        self.assertEqual(victim.get("/api/auth/me").status_code, 401)

    def test_user_confirmation_and_permissions(self):
        built = self.build_users()
        for confirm in (None, "", "wrong@x.test", 5):
            response = self.delete_user(self.admin, built.victim, confirm=confirm)
            self.assertEqual(response.status_code, 400, confirm)
        self.assertEqual(self.delete_user(self.member, built.victim).status_code, 401)
        self.assertEqual(self.delete_user(self.client_for("friend@x.test"), built.victim).status_code, 403)
        self.assertEqual(self.delete_user(self.admin, "missing").status_code, 404)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(User, built.victim))

    def test_self_and_last_admin_are_protected(self):
        with self.app.app_context():
            admin_id = User.query.filter_by(email=ADMIN).one().id
        own = self.delete_user(self.admin, admin_id, confirm=ADMIN)
        self.assertEqual((own.status_code, own.get_json()["error"]), (400, "cannot delete your own account"))
        preview = self.admin.get(f"/api/admin/users/{admin_id}/deletion-impact").get_json()
        self.assertTrue(preview["guards"]["is_self"] and preview["guards"]["is_last_admin"] and not preview["can_delete"])
        ghost = SimpleNamespace(id="ghost", role="admin", name="g", email="g@x.test")
        with patch("platform_api.routes.manage.current_user", return_value=ghost):
            last = self.delete_user(self.admin, admin_id, confirm=ADMIN)
        self.assertEqual((last.status_code, last.get_json()["error"]), (400, "cannot delete the last administrator"))
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(User, admin_id))

    def test_user_blockers_change_nothing(self):
        built = self.build_users()
        with self.app.app_context():
            db.session.get(ComputeSession, built.solo.session.id).state = "running"
            db.session.commit()
        blocked = self.delete_user(self.admin, built.victim)
        self.assertEqual((blocked.status_code, blocked.get_json()["error"]), (409, "active compute sessions exist"))
        preview = self.admin.get(f"/api/admin/users/{built.victim}/deletion-impact").get_json()
        self.assertFalse(preview["can_delete"])
        self.assertEqual(preview["blockers"][0]["code"], "active_compute_sessions")
        with self.app.app_context():
            db.session.get(ComputeSession, built.solo.session.id).state = "finished"
            comp = db.session.get(Competition, built.comp)
            comp.config = {"reviewing": {"locked_at": "2026-01-01T00:00:00+00:00"}}
            db.session.commit()
        locked = self.delete_user(self.admin, built.victim)
        self.assertEqual(locked.status_code, 409)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(User, built.victim))
            self.assertIsNotNone(db.session.get(Team, built.solo.team.id))
        self.assertTrue((self.uploads / "staged.bin").exists())

    def test_locked_review_blocks_reviewer_deletion(self):
        with self.app.app_context():
            comp, track, problem = self.competition("rev-comp")
            captain = self.user("rc@x.test")
            work = self.team_with_work(comp, track, problem, captain)
            reviewer = User.query.filter_by(role="reviewer").first()
            comp.config = {"reviewing": {"locked_at": "2026-01-01T00:00:00+00:00"}}
            db.session.commit()
            reviewer_email, reviewer_id = reviewer.email, reviewer.id
        response = self.delete_user(self.admin, reviewer_id, confirm=reviewer_email)
        self.assertEqual((response.status_code, response.get_json()["error"]), (409, "user has reviews in locked competitions"))
        self.assertTrue(self.exists(User, reviewer_id))


if __name__ == "__main__":
    unittest.main()

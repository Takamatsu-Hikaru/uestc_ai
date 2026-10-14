"""Lease-owned append-only logs using existing private artifact storage."""
import codecs
import hmac
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app, request
from sqlalchemy import select

from evaluation_log_safety import LOG_SOURCES, MAX_LOG_CHUNK, redact_evaluation_details, redact_log
from .extensions import db
from .models import EvaluationRun, new_id
from .progress_models import EvaluationArtifact
from .evaluation_trials import can_view_result
from .security import hash_token


def log_parts(name):
    import re
    match = re.fullmatch(r'attempt-([1-9][0-9]*)-(worker|agent|controller|diagnostics|environment)\.log', name)
    return (int(match[1]), match[2]) if match else None


def allowed_log(artifact):
    parts = log_parts(artifact.name)
    return bool(parts and can_view_result(artifact.run))


def append_log(run, source, offset, text):
    # Serializes all streams on this run, including first artifact creation.
    db.session.execute(select(EvaluationRun).where(EvaluationRun.id == run.id).with_for_update()).scalar_one()
    db.session.refresh(run)
    supplied = request.headers.get('X-Evaluation-Lease', '')
    expiry = run.lease_expires_at
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if (run.status != 'running' or not run.lease_hash or not supplied
            or not hmac.compare_digest(run.lease_hash, hash_token(supplied))
            or not expiry or expiry <= datetime.now(timezone.utc)):
        return {'error': 'evaluation lease invalid or expired'}, 403
    if source not in LOG_SOURCES or type(offset) is not int or offset < 0 or not isinstance(text, str):
        return {'error': 'invalid log chunk'}, 400
    if len(text.encode('utf-8')) > MAX_LOG_CHUNK:
        return {'error': 'log chunk exceeds 64 KiB'}, 413
    safe = redact_log(text, [supplied, current_app.config.get('EVALUATION_WORKER_TOKEN')])
    safe = redact_evaluation_details(safe)
    payload = safe.encode('utf-8')
    name = f'attempt-{run.attempts}-{source}.log'
    artifact = EvaluationArtifact.query.filter_by(run_id=run.id, name=name).first()
    size = artifact.size if artifact else 0
    root = Path(current_app.config['UPLOAD_FOLDER'])
    target = root / (artifact.storage_name if artifact else new_id() + '.log')
    if offset != size:
        # A lost HTTP acknowledgement must not duplicate an already written chunk.
        if artifact and offset < size:
            with target.open('rb') as stream:
                stream.seek(offset)
                duplicate = stream.read(len(payload)) == payload
            if duplicate:
                return {'offset': offset + len(payload)}, 200
        return {'error': 'log offset differs', 'offset': size}, 409
    if not payload:
        return {'offset': size}, 200
    try:
        with target.open('ab') as stream:
            stream.write(payload)
        if artifact:
            artifact.size = size + len(payload)
        else:
            artifact = EvaluationArtifact(run=run, name=name, storage_name=target.name, size=len(payload))
            db.session.add(artifact)
        db.session.commit()
    except Exception:
        db.session.rollback()
        if size:
            with target.open('r+b') as stream: stream.truncate(size)
        else:
            target.unlink(missing_ok=True)
        raise
    return {'offset': artifact.size}, 200


def read_log_chunk(artifact, offset, limit):
    if offset > artifact.size:
        offset = artifact.size
    with (Path(current_app.config['UPLOAD_FOLDER']) / artifact.storage_name).open('rb') as stream:
        stream.seek(offset)
        raw = stream.read(limit)
    decoder = codecs.getincrementaldecoder('utf-8')('replace')
    text = decoder.decode(raw, final=offset + len(raw) >= artifact.size)
    pending = decoder.getstate()[0]
    return {'text': text, 'offset': offset + len(raw) - len(pending), 'size': artifact.size}

import json
import re
import struct
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from ..extensions import db
from ..models import new_id
from ..progress_models import EvaluationArtifact
from ..evaluation_trials import can_view_result
from ..security import require_user
from ..uploading import save_with_limit
from .evaluations import leased_run
from ..run_logs import allowed_log, append_log, log_parts, read_log_chunk
from ..models import EvaluationRun

evidence_bp = Blueprint("evaluation_evidence", __name__)
MAX_FILE = 25 * 1024 * 1024


@evidence_bp.post("/evaluation-worker/runs/<run_id>/evidence")
def upload_evidence(run_id):
    run = leased_run(run_id)
    if not run:
        return jsonify({"error": "evaluation lease invalid or expired"}), 403
    file = request.files.get("file")
    name = request.form.get("name", "")
    if not file or not re.fullmatch(r"scene-[1-9][0-9]?-(?:replay\.(?:gif|mp4)|trajectory\.json|classification\.json)", name):
        return jsonify({"error": "invalid evidence name"}), 400
    if int(name.split('-')[1]) > run.config_snapshot["resources"]["episodes"]:
        return jsonify({"error": "invalid evidence scene"}), 400
    existing = EvaluationArtifact.query.filter_by(run_id=run.id, name=name).first()
    if not existing and EvaluationArtifact.query.filter_by(run_id=run.id).filter(~EvaluationArtifact.name.endswith('.log')).count() >= 90:
        return jsonify({"error": "evidence limit reached"}), 413
    storage = new_id() + Path(name).suffix
    target = Path(current_app.config["UPLOAD_FOLDER"]) / storage
    try:
        size = save_with_limit(file.stream, target, MAX_FILE)
        if name.endswith('.gif'):
            with target.open('rb') as image:
                header = image.read(10)
            if len(header) != 10 or header[:6] not in {b'GIF87a', b'GIF89a'}:
                raise ValueError("invalid replay image")
            width, height = struct.unpack('<HH', header[6:10])
            if not 1 <= width <= 1024 or not 1 <= height <= 1024:
                raise ValueError("invalid replay dimensions")
        elif name.endswith('.mp4'):
            with target.open('rb') as video:
                header = video.read(32)
            if len(header) < 24 or header[4:8] != b'ftyp' or header[8:12] not in {b'isom', b'iso2', b'avc1', b'mp41', b'mp42'}:
                raise ValueError("invalid replay video")
        else:
            content = json.loads(target.read_text(encoding='utf-8'))
            if not isinstance(content, (dict, list)):
                raise ValueError("invalid evidence JSON")
    except (ValueError, OSError) as error:
        target.unlink(missing_ok=True)
        return jsonify({"error": str(error)[:200]}), 400
    old = existing.storage_name if existing else None
    if existing:
        existing.storage_name, existing.size = storage, size
    else:
        existing = EvaluationArtifact(run=run, name=name, storage_name=storage, size=size)
        db.session.add(existing)
    db.session.commit()
    if old:
        (target.parent / old).unlink(missing_ok=True)
    return jsonify(existing.to_dict()), 201


@evidence_bp.get("/evaluation-artifacts/<artifact_id>")
@require_user()
def evidence(artifact_id):
    artifact = db.session.get(EvaluationArtifact, artifact_id)
    if not artifact or not can_view_result(artifact.run) or (log_parts(artifact.name) and not allowed_log(artifact)):
        return jsonify({"error": "evidence not found"}), 404
    response = send_from_directory(current_app.config["UPLOAD_FOLDER"], artifact.storage_name,
                                   as_attachment=not artifact.name.endswith('.mp4'), download_name=artifact.name)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@evidence_bp.post('/evaluation-worker/runs/<run_id>/logs/<source>')
def upload_log(run_id, source):
    run = leased_run(run_id)
    if not run:
        return jsonify({'error': 'evaluation lease invalid or expired'}), 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != {'offset', 'text'}:
        return jsonify({'error': 'invalid log chunk'}), 400
    body, status = append_log(run, source, data['offset'], data['text'])
    return jsonify(body), status


@evidence_bp.get('/evaluation-runs/<run_id>/logs')
@require_user()
def list_logs(run_id):
    run = db.session.get(EvaluationRun, run_id)
    if not run or not can_view_result(run):
        return jsonify({'error': 'logs not found'}), 404
    items = []
    for artifact in run.artifacts:
        if not allowed_log(artifact): continue
        attempt, source = log_parts(artifact.name)
        items.append({**artifact.to_dict(), 'attempt': attempt, 'source': source})
    response = jsonify({'items': sorted(items, key=lambda item: (item['attempt'], item['source']))})
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@evidence_bp.get('/evaluation-logs/<artifact_id>')
@require_user()
def log_content(artifact_id):
    artifact = db.session.get(EvaluationArtifact, artifact_id)
    if not artifact or not allowed_log(artifact):
        return jsonify({'error': 'logs not found'}), 404
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 65536))
        if offset < 0 or not 1 <= limit <= 65536: raise ValueError()
    except ValueError:
        return jsonify({'error': 'invalid log range'}), 400
    response = jsonify(read_log_chunk(artifact, offset, limit))
    response.headers['Cache-Control'] = 'private, no-store'
    return response

"""Package the contestant's project and trained weights for classification evaluation."""
import argparse
import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path


CACHE_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache",
              ".mypy_cache", ".ruff_cache", "node_modules"}
PRIVATE_NAMES = {".env", "credentials.json", "credentials.yaml", "credentials.yml",
                 "id_rsa", "id_ed25519", "id_ecdsa"}
MANIFEST_NAME = "package-manifest.json"


def check_member(path):
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"include must be a project-relative file: {path}")
    if any(part in CACHE_DIRS for part in path.parts):
        raise ValueError(f"cache or environment file cannot be included: {path}")
    name = path.name.lower()
    if (name in PRIVATE_NAMES or name.startswith(".env.")
            or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}):
        raise ValueError(f"credential/key file cannot be included: {path}")
    if "\\" in path.as_posix() or path.as_posix() == MANIFEST_NAME:
        raise ValueError(f"reserved or invalid package path: {path}")


def project_file(project, relative):
    check_member(relative)
    source = project / relative
    # Do not follow links into another checkout, data directory, or credential store.
    current = project
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"symlink cannot be included: {relative}")
    if not source.is_file() or not source.resolve().is_relative_to(project):
        raise ValueError(f"project file is missing or outside the project: {relative}")
    return source


def build(project, weights, output, includes=()):
    project = project.resolve(strict=True)
    if not project.is_dir():
        raise ValueError("--project must be a directory")
    weights = weights.resolve(strict=True)
    if not weights.is_file():
        raise ValueError("provide trained safetensors weights")
    config_file = project_file(project, Path("config.json"))
    if config_file.stat().st_size > 64 * 1024:
        raise ValueError("config.json exceeds 64 KB")
    config = json.loads(config_file.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict) or config.get("num_classes") != 40:
        raise ValueError("config.json must declare num_classes=40")
    weight_name = config.get("weights_file")
    if (not isinstance(weight_name, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", weight_name)
            or weight_name in {".", "..", "config.json", "inference.py", MANIFEST_NAME}
            or not weight_name.endswith(".safetensors")):
        raise ValueError("weights_file must name a safetensors file at the ZIP root")
    if "weights" in config:
        raise ValueError("local --weights packaging requires weights_file; remove the remote weights declaration")

    files = {"config.json": config_file,
             "inference.py": project_file(project, Path("inference.py"))}
    # Python modules are copied from the student's project, including subpackages.
    # Data, logs, archives and credentials are not recursively copied.
    for directory, dirs, names in os.walk(project, followlinks=False):
        base = Path(directory)
        dirs[:] = sorted(name for name in dirs
                         if name not in CACHE_DIRS and not (base / name).is_symlink())
        for name in sorted(names):
            if name.endswith(".py"):
                relative = (base / name).relative_to(project)
                files[relative.as_posix()] = project_file(project, relative)
    for value in includes:
        relative = Path(value)
        files[relative.as_posix()] = project_file(project, relative)
    if weight_name in files:
        raise ValueError("weights_file conflicts with an included project file")
    files[weight_name] = weights
    if len(files) + 1 > 256:
        raise ValueError("package exceeds 256 files including its manifest")
    if sum(path.stat().st_size for path in files.values()) > 64 * 1024**2:
        raise ValueError("package exceeds the 64 MB extracted limit; use the remote-weight protocol for larger weights")

    records = []
    output = output.resolve()
    if output in {path.resolve() for path in files.values()}:
        raise ValueError("output must not overwrite a project input")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=output.name + ".", suffix=".tmp", dir=output.parent)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED,
                             strict_timestamps=False) as archive:
            for name, source in sorted(files.items()):
                data = source.read_bytes()
                archive.writestr(name, data)
                records.append({"path": name, "size": len(data),
                                "sha256": hashlib.sha256(data).hexdigest()})
            manifest = {"version": 1, "files": records}
            manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
            if sum(row["size"] for row in records) + len(manifest_bytes) > 64 * 1024**2:
                raise ValueError("package and manifest exceed the 64 MB extracted limit")
            archive.writestr(MANIFEST_NAME, manifest_bytes)
        if Path(temporary).stat().st_size > 20 * 1024**2:
            raise ValueError("package exceeds the 20 MB ZIP limit; use the remote-weight protocol for larger weights")
        os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True,
                        help="student project containing inference.py and config.json")
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include", action="append", default=[], metavar="RELATIVE_FILE",
                        help="additional runtime asset, relative to --project; repeat for multiple files")
    args = parser.parse_args()
    try:
        manifest = build(args.project, args.weights, args.output, args.include)
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    print(args.output)
    for row in manifest["files"]:
        print(f"{row['sha256']}  {row['size']:>10}  {row['path']}")


if __name__ == "__main__":
    main()

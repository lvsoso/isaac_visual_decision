#!/usr/bin/env python3
"""Download a pinned COMPLETE HF snapshot; never execute its inference.py here."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

DEFAULT_REVISION = "0e5e6aa7d6d750e2b1504ba11a8136cb58aeb3cd"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-id", default="internlm/Intern-Decision-4B")
    p.add_argument("--revision", default=None, help="4B defaults to verified published commit; other sizes require an explicit revision")
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    revision = args.revision or (DEFAULT_REVISION if args.model_id == "internlm/Intern-Decision-4B" else None)
    if revision is None:
        p.error("Provide --revision for a different checkpoint. Never reuse another size's inference.py/calibration.")
    from huggingface_hub import HfApi, snapshot_download
    info = HfApi().model_info(args.model_id, revision=revision)
    resolved = info.sha
    root = args.output.expanduser().resolve()
    # Avoid mixing files from different snapshots in one local directory.
    receipt = root / "DOWNLOAD_RECEIPT.json"
    pending = root / "DOWNLOAD_IN_PROGRESS.json"
    if root.exists() and any(root.iterdir()):
        existing = receipt if receipt.exists() else pending
        if not existing.exists():
            p.error("Output is nonempty without a download receipt; choose a new directory to avoid mixing snapshots")
        prior = json.loads(existing.read_text())
        if prior.get("repo_id") != args.model_id or prior.get("resolved_revision") != resolved:
            p.error("Output contains a different checkpoint; choose a new directory")
    root.mkdir(parents=True, exist_ok=True)
    # An interrupted download can resume only for this exact resolved snapshot.
    pending.write_text(json.dumps({"repo_id": args.model_id, "resolved_revision": resolved}, indent=2)+"\n")
    snapshot_download(repo_id=args.model_id, revision=resolved, local_dir=root)
    required = ["inference.py", "config.json", "requirements.txt", "tokenizer_config.json", "preprocessor_config.json", "chat_template.jinja"]
    missing = [n for n in required if not (root/n).is_file()]
    index = root / "model.safetensors.index.json"
    if index.exists():
        mapping = json.loads(index.read_text())["weight_map"]
        for name in set(mapping.values()):
            candidate = (root / name).resolve()
            if root not in candidate.parents:
                raise RuntimeError("Invalid weight path in checkpoint index")
            if not candidate.is_file():
                missing.append(name)
    elif not (root / "model.safetensors").exists():
        missing.append("model.safetensors(.index.json)")
    if missing:
        raise RuntimeError(f"Incomplete snapshot: {missing}")
    # Hash small contract/config files. Large weight hashes are in the download cache;
    # the resolved immutable repo revision identifies the whole snapshot.
    hashes = {n: hashlib.sha256((root/n).read_bytes()).hexdigest() for n in required}
    data = {"repo_id": args.model_id, "requested_revision": revision, "resolved_revision": resolved,
            "contract_sha256": hashes, "local_path": str(root), "executed_remote_code": False}
    receipt.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n")
    pending.unlink(missing_ok=True)
    print(json.dumps(data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

# Third-party notice

The MIT license in this directory covers the newly supplied integration code
and documentation only. It does not relicense any external application,
robot asset, pretrained weights, downloaded inference script, or dependency.

- NVIDIA Isaac Sim is installed and licensed separately. This package does not
  bundle its installer, binaries, robot USDs, or its full tutorial source.
- The inspected NVIDIA `tutorial_9_pick_place_cumotion.py` source carries
  NVIDIA copyright 2021–2026 and SPDX Apache-2.0. The adapter loads a trusted
  locally installed copy; retain that file's original notices.
- Intern-Decision checkpoints, their `inference.py`, and any base-model
  materials are downloaded separately from the official repository and
  remain governed by their own licenses and notices.
- Python packages and ffmpeg remain subject to their respective licenses.

The test fixtures are synthetic. They contain no real robot captures or model
benchmark results. No external fonts, model weights, or videos are included.

See `docs/来源与改动.md` for source locations and the fixed model revision.

---
name: learn-this-project
description: Load core knowledge of the aws_lbd_art_builder_core project — its role in the 1+N package family, what it provides, and pointers to detailed architectural docs. Use when answering questions about this codebase, adding features, writing tests, or building a sub-package on top of this one.
---

# aws_lbd_art_builder_core — Project Knowledge

## What this package does

`aws_lbd_art_builder_core` is the **shared base** in a 1+N family of Lambda artifact builder packages:

- **1 core package** (this one): tool-agnostic infrastructure — path layouts, S3 layouts, credentials, packaging, upload, publish, source artifact build
- **N tool-specific packages**: each implements Step 1 (dependency installation) and wires the 4-step workflow together

| Package | Role |
|---------|------|
| `aws_lbd_art_builder_core` | Shared infrastructure (this package) |
| `aws_lbd_art_builder_uv` | UV-specific Step 1 builder + Workflow class |
| `aws_lbd_art_builder_pip` | Pip-specific Step 1 builder + Workflow class |
| `aws_lbd_art_builder_poetry` | Poetry-specific Step 1 builder + Workflow class |

**Core never calls `pip install`, `uv sync`, or `poetry install` directly.** Those belong in tool-specific sub-packages.

Core provides two workflows:

1. **Lambda layer workflow** (Steps 2–4): package → upload → publish. Sub-packages supply Step 1 (dependency installation).
2. **Lambda source deployment workflow**: copy/filter source → pip install --no-deps → zip → upload to S3.

It also provides pure-convention implementations: path layout managers, S3 layout managers, credentials handling, and abstract base classes for sub-package authors to extend.

---

## Detailed Architecture

For full architectural documentation, read the Maintainer Guide RST files:

- `docs/source/99-Maintainer-Guide/index.rst` — Maintainer Guide table of contents
- `docs/source/99-Maintainer-Guide/01-Project-Overview/index.rst` — Project overview and goals
- `docs/source/99-Maintainer-Guide/02-Code-Architect-Design/index.rst` — Complete module map, 4-step workflow details (Steps 2/3/4), source deployment workflow, path/S3 layout managers, Credentials, abstract base classes, public API by audience, and testing philosophy
- `docs/source/99-Maintainer-Guide/03-Sub-Package-Extension-Guide/index.rst` — How tool-specific sub-packages extend core: what to override (step_2/3/4), full builder example, end-to-end workflow, container builds, key design decisions

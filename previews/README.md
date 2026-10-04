# previews

Preview videos for the owner's visual approvals, one folder per pull request (`previews/<pr-number>/`). This branch
is never merged: the MP4s (10–30 MB each) would otherwise stay in main's history for good. They are rendered on a
RunPod GPU by `tools/gpu_preview.py` (see its `--publish`), and the coordinator fetches them from here.

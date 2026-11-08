#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(cd "${repo_dir}/.." && pwd)"
crew_dir="${workspace_dir}/CREW"

if [[ ! -d "${crew_dir}/ORCH/.git" || ! -d "${crew_dir}/WILDFIRE-ORCH/.git" ]]; then
  echo "Expected CREW source repositories were not found next to this snapshot." >&2
  exit 1
fi

mkdir -p "${repo_dir}/ORCH" "${repo_dir}/WILDFIRE-ORCH" "${repo_dir}/workspace"

# Copy the ORCH tracked working tree, preserving local modifications but not its .git directory.
git -C "${crew_dir}/ORCH" ls-files -z \
  | rsync -a --from0 --files-from=- "${crew_dir}/ORCH/" "${repo_dir}/ORCH/"

# Include the new, currently untracked implementation packages.
rsync -a \
  --exclude='__pycache__/' --exclude='*.pyc' \
  "${crew_dir}/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/coordination/" \
  "${repo_dir}/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/coordination/"
rsync -a \
  --exclude='__pycache__/' --exclude='*.pyc' \
  "${crew_dir}/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/config/resource_scheduling/" \
  "${repo_dir}/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/config/resource_scheduling/"

# Copy the Unity file changed locally, retaining its upstream path for easy comparison.
unity_rel="crew-dojo/Unity/Assets/Examples/Wildfire/Scripts/MapManager.cs"
mkdir -p "${repo_dir}/WILDFIRE-ORCH/$(dirname "${unity_rel}")"
rsync -a "${crew_dir}/WILDFIRE-ORCH/${unity_rel}" "${repo_dir}/WILDFIRE-ORCH/${unity_rel}"

# Copy CREW-level reports, scripts, and tests while excluding bulky/generated evidence.
rsync -a --delete \
  --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.pdf' \
  --exclude='*.tar' --exclude='*.tar.gz' --exclude='*.zip' \
  --exclude='*.jsonl' --exclude='*_native_log_prefix.txt' \
  "${crew_dir}/research/" "${repo_dir}/workspace/research/"
rsync -a --delete --exclude='__pycache__/' --exclude='*.pyc' \
  "${crew_dir}/scripts/" "${repo_dir}/workspace/scripts/"
rsync -a --delete --exclude='__pycache__/' --exclude='*.pyc' \
  "${crew_dir}/tests/" "${repo_dir}/workspace/tests/"

find "${crew_dir}" -maxdepth 1 -type f \( -name '*.md' -o -name '*.py' -o -name '*.sh' \) -print0 \
  | xargs -0 -r -I{} rsync -a "{}" "${repo_dir}/workspace/"

echo "Workspace synchronized. Review with: git -C '${repo_dir}' status --short"

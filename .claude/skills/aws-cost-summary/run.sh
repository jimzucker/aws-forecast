#!/usr/bin/env bash
#
# Wrapper invoked by the aws-cost-summary Claude skill.
# Sets the AWS profile + region env vars get_forecast.py reads, then executes
# it inside an isolated venv so we don't trip PEP 668 on system Pythons.
#
# Copyright 2026 Jim Zucker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
set -euo pipefail

export GET_FORECAST_AWS_PROFILE="${AWS_COST_PROFILE:-aws-cost-readonly}"
# Cost Explorer is a global service but the SDK still demands a region. Default
# so a profile configured without one (common: pressing Enter on `aws configure`)
# doesn't fail with an inscrutable NoRegionError before reaching CE.
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

# Resolve repo root: this script lives at <repo>/.claude/skills/aws-cost-summary/run.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# PEP 668 (Homebrew/Debian/Ubuntu Python ≥3.11) blocks `pip install` against the
# system interpreter. Lambda's runtime ships boto3, but locally we have to
# provide it ourselves — isolate in a venv next to the repo. First run creates
# it; subsequent runs reuse.
VENV="$REPO_ROOT/.venv-skill"
if [[ ! -x "$VENV/bin/python" ]]; then
    echo "[aws-cost-summary] First run: creating venv at $VENV" >&2
    python3 -m venv "$VENV" >&2
    "$VENV/bin/pip" install --quiet --upgrade pip >&2
    "$VENV/bin/pip" install --quiet boto3 'python-dateutil>=2.8,<3' >&2
fi

exec "$VENV/bin/python" "$REPO_ROOT/get_forecast.py"

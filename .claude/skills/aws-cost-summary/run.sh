#!/usr/bin/env bash
# Wrapper invoked by the aws-cost-summary Claude skill.
# Sets the AWS profile env var that get_forecast.py reads, then executes it.
set -euo pipefail

export GET_FORECAST_AWS_PROFILE="${AWS_COST_PROFILE:-aws-cost-readonly}"

# Resolve repo root: this script lives at <repo>/.claude/skills/aws-cost-summary/run.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

exec python3 "$REPO_ROOT/get_forecast.py"

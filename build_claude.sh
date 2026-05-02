#!/usr/bin/env bash
#
# Build and upload the Claude connector Lambda zip.
#
# Required env vars:
#   LAMBDA_BUCKET   S3 bucket to upload the zip to (must already exist).
#
# Optional env vars:
#   AWS_PROFILE     AWS named profile to use for the s3 cp.
#   AWS_REGION      AWS region (also passed to s3 cp via --region).
#   ZIP_KEY         S3 key (default: claude_connector.zip).
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

if [[ -z "${LAMBDA_BUCKET:-}" ]]; then
  echo "ERROR: LAMBDA_BUCKET env var is required" >&2
  exit 1
fi

ZIP_KEY="${ZIP_KEY:-claude_connector.zip}"

cd "$(dirname "$0")"

rm -rf target
mkdir -p target/build

# PEP 668 (Homebrew/Debian/Ubuntu Python ≥3.11) blocks `pip install` against
# the system interpreter. Use a venv's pip — its `--target` install isn't
# externally-managed. First run creates the venv; subsequent runs reuse.
VENV=".venv-build"
if [[ ! -x "$VENV/bin/pip" ]]; then
    echo "[build_claude] First run: creating venv at $VENV" >&2
    python3 -m venv "$VENV" >&2
    "$VENV/bin/pip" install --quiet --upgrade pip >&2
fi

# Vendor python-dateutil (the one non-stdlib import in get_forecast.py).
"$VENV/bin/pip" install --quiet --target target/build -r requirements.txt

# Bundle source files alongside the deps.
cp get_forecast.py claude_connector_handler.py target/build/

cd target/build
zip -qr "../${ZIP_KEY}" .
cd ..

aws_args=()
if [[ -n "${AWS_PROFILE:-}" ]]; then aws_args+=(--profile "$AWS_PROFILE"); fi
if [[ -n "${AWS_REGION:-}" ]]; then aws_args+=(--region "$AWS_REGION"); fi

aws "${aws_args[@]}" s3 cp "${ZIP_KEY}" "s3://${LAMBDA_BUCKET}/${ZIP_KEY}"

echo "Uploaded s3://${LAMBDA_BUCKET}/${ZIP_KEY}"

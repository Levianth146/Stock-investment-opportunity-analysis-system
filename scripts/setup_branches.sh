#!/usr/bin/env bash
# N1 chạy 1 lần sau khi đã push skeleton lên main: tạo develop + nhánh feature cho từng module.
set -euo pipefail
git checkout main && git pull origin main
git checkout -B develop && git push -u origin develop
for b in core-pipeline m1-data m2-fundamental m3-technical m4-valuation m5-sentiment m6-risk m7-scoring m8-validate m9-report; do
  git checkout -B "feat/$b" develop
  git push -u origin "feat/$b"
done
git checkout develop
echo "Xong. Bật branch protection cho main + develop (Require PR, Require status checks: test)."

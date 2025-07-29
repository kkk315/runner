#!/bin/bash
set -e
SECRET_FILE="${1:-secrets.env}"
while IFS= read -r line; do
  [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
  key="${line%%=*}"
  value="${line#*=}"
  echo "$value" | docker secret create "$key" -
done < "$SECRET_FILE"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/infra/.build"

RUNTIME_REQ="${ROOT_DIR}/requirements.txt"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LAMBDA_PY_VERSION="${LAMBDA_PY_VERSION:-311}"
LAMBDA_PLATFORM="${LAMBDA_PLATFORM:-manylinux2014_x86_64}"

clean() {
  rm -rf "${BUILD_DIR}"
  mkdir -p "${BUILD_DIR}"
}

pip_install_runtime_deps() {
  local target_dir="$1"

  # When running on macOS/Windows, we still want Lambda-compatible wheels.
  # This is critical for packages with native extensions (e.g., pydantic-core).
  local uname_out
  uname_out="$(uname -s || true)"

  if [[ "${uname_out}" == "Linux" ]]; then
    "${PYTHON_BIN}" -m pip install -r "${RUNTIME_REQ}" -t "${target_dir}" --no-compile >/dev/null
    return
  fi

  "${PYTHON_BIN}" -m pip install \
    -r "${RUNTIME_REQ}" \
    -t "${target_dir}" \
    --only-binary=:all: \
    --platform "${LAMBDA_PLATFORM}" \
    --implementation cp \
    --python-version "${LAMBDA_PY_VERSION}" \
    --no-compile >/dev/null
}

build_lambda_zip() {
  local name="$1"
  local src_dir="$2"
  local out_zip="$3"

  local work_dir="${BUILD_DIR}/${name}"
  rm -rf "${work_dir}"
  mkdir -p "${work_dir}"

  pip_install_runtime_deps "${work_dir}"
  cp -R "${src_dir}/." "${work_dir}/"

  (cd "${work_dir}" && zip -qr "${out_zip}" .)
}

build_shared_layer_zip() {
  local out_zip="$1"

  local layer_dir="${BUILD_DIR}/shared_layer"
  rm -rf "${layer_dir}"
  mkdir -p "${layer_dir}/python/shared"

  cp -R "${ROOT_DIR}/src/shared/shared/." "${layer_dir}/python/shared/"
  (cd "${layer_dir}" && zip -qr "${out_zip}" .)
}

clean

AUTH_ZIP="${BUILD_DIR}/auth.zip"
CART_ZIP="${BUILD_DIR}/cart.zip"
LAYER_ZIP="${BUILD_DIR}/shared_layer.zip"

build_lambda_zip "auth" "${ROOT_DIR}/src/auth" "${AUTH_ZIP}"
build_lambda_zip "cart" "${ROOT_DIR}/src/cart" "${CART_ZIP}"
build_shared_layer_zip "${LAYER_ZIP}"

echo "Built: ${AUTH_ZIP}"
echo "Built: ${CART_ZIP}"
echo "Built: ${LAYER_ZIP}"


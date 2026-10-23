#!/bin/bash
# Furby AI systemd サービスのインストール・有効化スクリプト
# 実行: sudo bash systemd/install_service.sh

set -e

SERVICE_NAME=furby.service
SERVICE_SRC="$(dirname "$(readlink -f "$0")")/${SERVICE_NAME}"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}"

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: sudo で実行してください"
    exit 1
fi

if [[ ! -f "${SERVICE_SRC}" ]]; then
    echo "ERROR: ${SERVICE_SRC} が見つかりません"
    exit 1
fi

echo "[1/4] サービスファイルをコピー: ${SERVICE_SRC} → ${SERVICE_DST}"
cp "${SERVICE_SRC}" "${SERVICE_DST}"

echo "[2/4] systemd デーモンをリロード"
systemctl daemon-reload

echo "[3/4] サービスを有効化（次回起動時から自動起動）"
systemctl enable ${SERVICE_NAME}

echo "[4/4] サービスを今すぐ起動"
systemctl restart ${SERVICE_NAME}

sleep 2
echo
echo "=== 現在の状態 ==="
systemctl status ${SERVICE_NAME} --no-pager || true

echo
echo "--- 便利コマンド ---"
echo "  ログ確認（リアルタイム）: journalctl -u ${SERVICE_NAME} -f"
echo "  停止                    : sudo systemctl stop ${SERVICE_NAME}"
echo "  起動                    : sudo systemctl start ${SERVICE_NAME}"
echo "  再起動                  : sudo systemctl restart ${SERVICE_NAME}"
echo "  自動起動を無効化        : sudo systemctl disable ${SERVICE_NAME}"

#!/usr/bin/env bash
# 用 Cloudflare Browser Rendering 对生产大屏各页面、各常规分辨率批量截图。
# 视口尺寸取「浏览器实际可视区域」，因为驾驶舱是 height:100dvh 铺满视口。
set -u
source ~/.env
T="$CF_DNS_TOKEN"; ACC="${CLOUDFLARE_ACCOUNT_ID:?set CLOUDFLARE_ACCOUNT_ID in ~/.env}"
API="https://api.cloudflare.com/client/v4/accounts/$ACC/browser-rendering/screenshot"
BASE="${MOD_PUBLIC_BASE_URL:?set MOD_PUBLIC_BASE_URL in ~/.env}"

declare -A PAGES=( [A]=dashboard [B]=construction [C]=rollout [D]=operations [E]=issues [F]=insights )
# 名称:宽:高  —— big=1920 全屏大屏；mbp=1800×1092 用户实机；k2=2560 2K；min=1366 压力
SIZES=( "big:1920:1080" "mbp:1800:1092" "k2:2560:1440" "min:1366:768" )

for sz in "${SIZES[@]}"; do
  IFS=: read -r nm w h <<< "$sz"
  for p in A B C D E F; do
    url="$BASE/${PAGES[$p]}"
    out="/tmp/shots/${p}_${nm}.png"
    code=$(curl -s -X POST "$API" -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
      -d "{\"url\":\"$url\",\"viewport\":{\"width\":$w,\"height\":$h,\"deviceScaleFactor\":1},\"gotoOptions\":{\"waitUntil\":\"load\",\"timeout\":30000},\"waitForTimeout\":4200,\"screenshotOptions\":{\"type\":\"png\"}}" \
      -o "$out" -w "%{http_code}")
    echo "${p}_${nm} -> HTTP:$code $(du -h "$out" 2>/dev/null | cut -f1)"
    sleep 1
  done
done
echo DONE

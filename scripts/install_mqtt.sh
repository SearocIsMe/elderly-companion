#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./install_mqtt.sh [--allow-anon] [--user USER --pass PASS] [--bind 127.0.0.1] [--port 1883]
#
# Examples:
#   ./install_mqtt.sh --allow-anon
#   ./install_mqtt.sh --user robot --pass mypass
#
# Notes:
# - On WSL (Ubuntu 22.04+), systemd is usually available now. If not, the script will still install mosquitto,
#   but you may need to start it manually: `sudo mosquitto -c /etc/mosquitto/mosquitto.conf -v`.
# - By default we bind to 127.0.0.1 for safety. Use --bind 0.0.0.0 if you need LAN access (and understand the risks).

BINDFACE="127.0.0.1"
PORT="1883"
ALLOW_ANON="false"
MQTT_USER="admin"
MQTT_PASS="DTC7788"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --allow-anon) ALLOW_ANON="true"; shift ;;
    --user)       MQTT_USER="$2"; shift 2 ;;
    --pass)       MQTT_PASS="$2"; shift 2 ;;
    --bind)       BINDFACE="$2"; shift 2 ;;
    --port)       PORT="$2"; shift 2 ;;
    -h|--help)
      grep '^#' "$0" | sed -e 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -n "$MQTT_USER" && -z "$MQTT_PASS" ]]; then
  echo "Error: --user provided but --pass missing" >&2
  exit 1
fi
if [[ "$ALLOW_ANON" == "true" && -n "$MQTT_USER" ]]; then
  echo "Error: choose either --allow-anon OR --user/--pass, not both" >&2
  exit 1
fi

echo ">>> Installing mosquitto broker & clients"
sudo apt-get update -y
sudo apt-get install -y mosquitto mosquitto-clients

CONF_DIR="/etc/mosquitto"
CONF_MAIN="${CONF_DIR}/mosquitto.conf"
CONF_D="${CONF_DIR}/conf.d"
CUSTOM_CONF="${CONF_D}/elderly.conf"
PASSFILE="${CONF_DIR}/passwd"

echo ">>> Writing main config (${CONF_MAIN})"
sudo bash -c "cat > '${CONF_MAIN}'" <<EOF
# Mosquitto main config (includes conf.d)
persistence true
persistence_location /var/lib/mosquitto/
log_timestamp true
include_dir ${CONF_D}
EOF

sudo mkdir -p "${CONF_D}"

if [[ "$ALLOW_ANON" == "true" ]]; then
  echo ">>> Creating anonymous listener at ${BINDFACE}:${PORT}"
  sudo bash -c "cat > '${CUSTOM_CONF}'" <<EOF
listener ${PORT} ${BINDFACE}
allow_anonymous true
persistence true
EOF
else
  echo ">>> Creating password-protected listener at ${BINDFACE}:${PORT}"
  if [[ -z "$MQTT_USER" ]]; then
    MQTT_USER="robot"
    MQTT_PASS="$(tr -dc A-Za-z0-9 </dev/urandom | head -c 16)"
    echo "    Generated credentials -> user: ${MQTT_USER}  pass: ${MQTT_PASS}"
  fi
  sudo touch "${PASSFILE}"
  sudo mosquitto_passwd -b "${PASSFILE}" "${MQTT_USER}" "${MQTT_PASS}"

  sudo bash -c "cat > '${CUSTOM_CONF}'" <<EOF
listener ${PORT} ${BINDFACE}
allow_anonymous false
password_file ${PASSFILE}
persistence true
EOF
fi

# Try to enable and start via systemd (works on Ubuntu/WSL with systemd enabled)
if command -v systemctl >/dev/null 2>&1; then
  echo ">>> Enabling & restarting mosquitto via systemd"
  sudo systemctl enable mosquitto || true
  sudo systemctl restart mosquitto
  sleep 1
  sudo systemctl --no-pager --full status mosquitto || true
else
  echo ">>> systemctl not found. You can run mosquitto manually:"
  echo "    sudo mosquitto -c ${CONF_MAIN} -v"
fi

echo
echo "========================================="
echo " MQTT broker ready"
echo "  - bind: ${BINDFACE}"
echo "  - port: ${PORT}"
if [[ "$ALLOW_ANON" == "true" ]]; then
  echo "  - auth: anonymous (allowed)"
else
  echo "  - auth: username/password"
  echo "  - user: ${MQTT_USER}"
  echo "  - pass: ${MQTT_PASS}"
fi
echo "========================================="
echo
echo "Quick tests (new terminal):"
if [[ "$ALLOW_ANON" == "true" ]]; then
  echo "  mosquitto_sub -h ${BINDFACE} -p ${PORT} -t test -v"
  echo "  mosquitto_pub -h ${BINDFACE} -p ${PORT} -t test -m 'hello'"
else
  echo "  mosquitto_sub -h ${BINDFACE} -p ${PORT} -u '${MQTT_USER}' -P '${MQTT_PASS}' -t test -v"
  echo "  mosquitto_pub -h ${BINDFACE} -p ${PORT} -u '${MQTT_USER}' -P '${MQTT_PASS}' -t test -m 'hello'"
fi

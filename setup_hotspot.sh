set -e

IFACE="wlan0"
CON_NAME="Hotspot"
SSID="$(cat /etc/hostname | tr -d '\n')"

if nmcli connection show "$CON_NAME" &>/dev/null; then
    echo "Профиль '$CON_NAME' уже существует, ничего не делаю."
    echo "Удалить и пересоздать: nmcli connection delete $CON_NAME"
    exit 0
fi

nmcli connection add \
    type wifi \
    ifname "$IFACE" \
    con-name "$CON_NAME" \
    autoconnect no \
    ssid "$SSID"

nmcli connection modify "$CON_NAME" \
    802-11-wireless.mode ap \
    802-11-wireless.band bg \
    ipv4.method shared

echo "Готово. Точка доступа '$SSID' создана (профиль '$CON_NAME')."
echo "Поднять вручную сейчас:   nmcli connection up $CON_NAME"
echo "Погасить:                 nmcli connection down $CON_NAME"

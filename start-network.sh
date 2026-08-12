IFACE="wlan0"
CON_NAME="Hotspot"
TIMEOUT=20

nmcli radio wifi on
sleep 2

for i in $(seq 1 "$TIMEOUT"); do
    STATE=$(nmcli -t -f GENERAL.STATE device show "$IFACE" | cut -d: -f2)
    if [[ "$STATE" == "100 (connected)" ]]; then
        echo "Подключены к известной сети, хотспот не нужен."
        exit 0
    fi
    sleep 1
done

echo "Известных сетей рядом нет — поднимаю хотспот."
nmcli connection up "$CON_NAME"

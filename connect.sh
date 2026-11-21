#!/bin/bash
# Verbindung Mac -> Roboter-PC (NEURA LARA) per Ethernet einrichten und prüfen.
#
#   ./connect.sh          # USB-LAN-Adapter automatisch suchen
#   ./connect.sh en7      # oder das Interface direkt angeben
#
# Die Adresse geht bei Neustart oder Abstecken verloren, also einmal pro Sitzung ausführen.
# Fragt nach dem Mac-Passwort (sudo), wenn die Adresse noch fehlt.

MAC_IP=192.168.2.10
ROBOT_IP=192.168.2.13
NEURAPY_PORT=65432

IFACE="$1"
if [ -z "$IFACE" ]; then
    # erstes Interface mit "LAN" oder "Ethernet" im Namen, das ein Kabel hat
    for dev in $(networksetup -listallhardwareports | awk '/Hardware Port: .*(LAN|Ethernet)/{getline; print $2}'); do
        if ifconfig "$dev" 2>/dev/null | grep -q "status: active"; then
            IFACE="$dev"
            break
        fi
    done
fi
if [ -z "$IFACE" ]; then
    echo "Kein Ethernet-Adapter mit Kabel gefunden. Adapter und Kabel prüfen, oder Interface angeben: ./connect.sh en7"
    exit 1
fi
echo "Adapter: $IFACE"

if ifconfig "$IFACE" | grep -q "inet $MAC_IP "; then
    echo "Adresse $MAC_IP ist schon gesetzt."
else
    echo "Setze $MAC_IP auf $IFACE (Mac-Passwort):"
    sudo ifconfig "$IFACE" alias "$MAC_IP" 255.255.255.0 || exit 1
fi

if ping -c 2 -t 3 "$ROBOT_IP" >/dev/null 2>&1; then
    echo "Ping $ROBOT_IP: ok"
else
    echo "Ping $ROBOT_IP: keine Antwort. Ist der Roboter-PC an und das Kabel am richtigen Port?"
    exit 1
fi

if nc -z -G 3 "$ROBOT_IP" "$NEURAPY_PORT" >/dev/null 2>&1; then
    echo "NeuraPy-Port $NEURAPY_PORT: offen"
else
    echo "NeuraPy-Port $NEURAPY_PORT: zu. Robotersoftware startet evtl. noch, in 1-2 Minuten nochmal versuchen."
    exit 1
fi

echo "Verbunden. Weboberfläche: http://$ROBOT_IP:8080   SSH: ssh hrg@$ROBOT_IP"

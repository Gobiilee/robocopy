// views/qml/NetworkTab.qml
import QtQuick
import QtQuick.Controls

Item {
    id: networkTabRoot

    Column {
        anchors.fill: parent
        spacing: 8

        // ── CREDENTIAL PANEL ─────────────────────────────────────────────────
        Rectangle {
            width: parent.width
            height: 90
            color: "#252525"
            radius: 6
            border.color: "#333333"

            Column {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 6

                Text { text: "SMB / NETWORK SHARE"; color: "#888888"; font.bold: true; font.pixelSize: 11 }

                Row {
                    width: parent.width
                    spacing: 6

                    TextField { id: ipIn; placeholderText: "Server IP"; width: 120 }
                    TextField { id: shareIn; placeholderText: "Share name"; width: 120 }
                    TextField { id: userIn; placeholderText: "Username"; width: 100 }
                    TextField { id: passIn; placeholderText: "Password"; echoMode: TextField.Password; width: 100 }

                    Button {
                        text: "⚡  Connect"
                        onClicked: (typeof networkVM !== "undefined" && networkVM) ? networkVM.connect_share(ipIn.text, userIn.text, passIn.text, shareIn.text) : null
                    }
                }
                
                // Resolved line 43: check context status text field initialization
                Text {
                    text: (typeof networkVM !== "undefined" && networkVM && networkVM.connection_status_text) ? networkVM.connection_status_text : "Not connected"
                    color: "#666666"
                    font.pixelSize: 11
                }
            }
        }

        // ── REMOTE FILES LISTVIEW ───────────────────────────────────────────
        Text { text: "REMOTE FILES"; color: "#555555"; font.bold: true; font.pixelSize: 11 }
        
        Rectangle {
            width: parent.width
            height: 180
            color: "#1e1e1e"
            border.color: "#333333"
            radius: 6

            ListView {
                anchors.fill: parent
                clip: true
                model: (typeof networkVM !== "undefined" && networkVM) ? networkVM.smb_items_model : null
                
                delegate: Row {
                    width: parent.width
                    spacing: 8
                    CheckBox {
                        checked: model.is_checked ? model.is_checked : false
                        onToggled: (typeof networkVM !== "undefined" && networkVM) ? networkVM.toggle_item_index(index, checked) : null
                    }
                    Text {
                        text: (model.is_dir ? "📁 " : "📄 ") + model.item_name
                        color: "#dddddd"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }

        // ── DOWNLOAD DESTINATION CARD ────────────────────────────────────────
        Row {
            width: parent.width
            spacing: 10
            TextField {
                id: netDstInput
                // Resolved line 87: fallback safe string assignment to QString channel
                text: (typeof networkVM !== "undefined" && networkVM && networkVM.download_destination) ? networkVM.download_destination : ""
                placeholderText: "Choose download destination folder…"
                width: parent.width - 90
            }
            Button {
                text: "Browse…"
                onClicked: networkViewWrapper.pick_net_destination()
            }
        }

        // ── DOWNLOAD TRIGGER ACTION BUTTON ───────────────────────────────────
        Button {
            width: parent.width
            height: 38
            text: (typeof networkVM !== "undefined" && networkVM && networkVM.is_busy) ? "■  Cancel Download" : "⬇  Download Selected"
            
            // Resolved line 102: convert dynamic evaluation directly into clean fallback boolean
            enabled: (typeof networkVM !== "undefined" && networkVM && networkVM.is_connect_ok) ? true : false
            
            background: Rectangle {
                color: (typeof networkVM !== "undefined" && networkVM && networkVM.is_busy) ? "#c62828" : "#1a73e8"
                radius: 6
            }
            onClicked: {
                if (networkVM.is_busy) {
                    networkVM.cancel_download();
                } else {
                    networkVM.start_download(netDstInput.text);
                }
            }
        }
    }
}
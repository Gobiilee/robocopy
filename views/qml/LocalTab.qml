// views/qml/LocalTab.qml
import QtQuick
import QtQuick.Controls

Item {
    id: localTabRoot

    // Use a Item-based layout layout wrapper instead of forcing anchors on sub-children
    Column {
        id: mainLayoutColumn
        anchors.fill: parent
        spacing: 12

        // ── SOURCE -> DESTINATION ROW ──────────────────────────────────────
        Row {
            width: parent.width
            spacing: 8

            // Source Folder Picker Box
            Rectangle {
                width: (parent.width - 24) / 2
                height: 60
                color: "#252525"
                radius: 6
                border.color: "#333333"

                Column {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 4
                    Text { text: "SOURCE"; color: "#777777"; font.bold: true; font.pixelSize: 10 }
                    Row {
                        width: parent.width
                        spacing: 6
                        Text { text: "📁"; font.pixelSize: 14 }
                        TextField {
                            id: srcInput
                            width: parent.width - 80
                            // Safe Navigation: fallback to empty string if context variable is undefined
                            text: (typeof localVM !== "undefined" && localVM) ? localVM.src_path : ""
                            placeholderText: "Choose source folder…"
                            readOnly: true
                            background: Rectangle { color: "#d7d7d7"; border.color: "#3a3a3a"; radius: 4 }
                        }
                        Button {
                            text: "Browse…"
                            width: 72
                            enabled: (typeof localVM !== "undefined" && localVM) ? !localVM.is_busy : true
                            onClicked: localViewWrapper.pick_source()
                        }
                    }
                }
            }

            Text {
                text: "→"
                color: "#d7d7d7"
                font.pixelSize: 20
                font.bold: true
                anchors.verticalCenter: parent.verticalCenter
            }

            // Destination Folder Picker Box
            Rectangle {
                width: (parent.width - 24) / 2
                height: 60
                color: "#252525"
                radius: 6
                border.color: "#333333"

                Column {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 4
                    Text { text: "DESTINATION"; color: "#777777"; font.bold: true; font.pixelSize: 10 }
                    Row {
                        width: parent.width
                        spacing: 6
                        Text { text: "📁"; font.pixelSize: 14 }
                        TextField {
                            id: dstInput
                            width: parent.width - 80
                            text: (typeof localVM !== "undefined" && localVM) ? localVM.dst_path : ""
                            placeholderText: "Choose destination folder…"
                            readOnly: true
                            background: Rectangle { color: "#d7d7d7"; border.color: "#3a3a3a"; radius: 4 }
                        }
                        Button {
                            text: "Browse…"
                            width: 72
                            enabled: (typeof localVM !== "undefined" && localVM) ? !localVM.is_busy : true
                            onClicked: localViewWrapper.pick_destination()
                        }
                    }
                }
            }
        }

        // ── STATS BAR PANEL ──────────────────────────────────────────────────
        Rectangle {
            width: parent.width
            height: 55
            color: "#252525"
            radius: 6
            border.color: "#333333"

            Row {
                anchors.top: parent.top
                anchors.margins: 6
                spacing: 40
                x: 14

                Column {
                    Text { text: "Speed"; color: "#d7d7d7"; font.pixelSize: 9 }
                    // Resolved line 116: safe conversion preventing [undefined] injection to QString
                    Text { text: (typeof localVM !== "undefined" && localVM && localVM.speed_text) ? localVM.speed_text : "— B/s"; color: "#e0e0e0"; font.bold: true }
                }
                Column {
                    Text { text: "ETA"; color: "#d7d7d7"; font.pixelSize: 9 }
                    Text { text: (typeof localVM !== "undefined" && localVM && localVM.eta_text) ? localVM.eta_text : "—"; color: "#e0e0e0"; font.bold: true }
                }
                Column {
                    Text { text: "Progress"; color: "#d7d7d7"; font.pixelSize: 9 }
                    Text { text: (typeof localVM !== "undefined" && localVM) ? (localVM.progress_pct + " %") : "0 %"; color: "#e0e0e0"; font.bold: true }
                }
            }

            ProgressBar {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 8
                height: 6
                value: (typeof localVM !== "undefined" && localVM) ? (localVM.progress_pct / 100) : 0
            }
        }

        // ── FILES BATCH TEXTAREA LOG ─────────────────────────────────────────
        Text { text: "FILES"; color: "#d7d7d7"; font.bold: true; font.pixelSize: 11 }
        ScrollView {
            width: parent.width
            // Define explicit height instead of anchoring inside a Column container
            height: 400 
            clip: true

            TextArea {
                // Resolved line 140: absolute defensive validation against undefined rich text values
                text: (typeof localVM !== "undefined" && localVM && localVM.files_html_log) ? localVM.files_html_log : ""
                textFormat: TextEdit.RichText
                readOnly: true
                background: Rectangle { color: "#1e1e1e"; border.color: "#333333"; radius: 6 }
            }
        }

        // ── BOTTOM ROW ACTION BAR ────────────────────────────────────────────
        Row {
            width: parent.width
            spacing: 12

            Text {
                text: "Threads:"
                color: "#d7d7d7"
                anchors.verticalCenter: parent.verticalCenter
            }

            SpinBox {
                id: threadSpin
                from: 1
                to: 64
                value: 16
                enabled: (typeof localVM !== "undefined" && localVM) ? !localVM.is_busy : true
            }

            Item { width: 10; height: 1 } 

            Button {
                id: actionBtn
                width: 160
                height: 36
                text: (typeof localVM !== "undefined" && localVM && localVM.is_busy) ? "■  Cancel" : "▶  Start Transfer"
                
                background: Rectangle {
                    color: (typeof localVM !== "undefined" && localVM && localVM.is_busy) ? "#c62828" : "#1a73e8"
                    radius: 6
                }

                onClicked: {
                    if (typeof localVM !== "undefined" && localVM && localVM.is_busy) {
                        localVM.cancel_copy();
                    } else {
                        localVM.start_copy(srcInput.text, dstInput.text, threadSpin.value);
                    }
                }
            }
        }
    }
}
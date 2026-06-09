// views/main_window.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

ApplicationWindow {
    id: mainWindow
    width: 780
    height: 720
    title: "pyRoboCopy"
    visible: true

    // Global Dark Palette Style
    background: Rectangle {
        color: "#1a1a1a"
    }

    // Top Navigation TabBar
    TabBar {
        id: tabBar
        width: parent.width
        currentIndex: viewStacked.currentIndex
        background: Rectangle { color: "#242424" }

        TabButton {
            text: "💻  Local"
            font.pixelSize: 12
            // Active state custom coloring
            contentItem: Text {
                text: parent.text
                color: parent.checked ? "#ffffff" : "#888888"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                color: parent.checked ? "#1a73e8" : "#242424"
            }
        }

        TabButton {
            text: "🌐  Network"
            font.pixelSize: 12
            contentItem: Text {
                text: parent.text
                color: parent.checked ? "#ffffff" : "#888888"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                color: parent.checked ? "#1a73e8" : "#242424"
            }
        }
    }

    // Stacked container to switch views seamlessly
    StackLayout {
        id: viewStacked
        anchors.top: tabBar.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 10
        currentIndex: tabBar.currentIndex

        LocalTab {
            id: localView
        }

        NetworkTab {
            id: networkView
        }
    }
}
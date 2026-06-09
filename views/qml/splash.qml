// views/splash.qml
import QtQuick
import QtQuick.Controls

Window {
    id: splashWindow
    width: 480
    height: 320
    visible: true
    
    // Cấu hình cửa sổ không viền, luôn nổi lên đầu
    flags: Qt.SplashScreen | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint
    color: "transparent"

    // Định vị giữa màn hình
    x: (Screen.width - width) / 2
    y: (Screen.height - height) / 2

    Rectangle {
        id: bg
        anchors.fill: parent
        color: "#1a1a1a"
        radius: 14
        border.color: "#2a2a2a"
        border.width: 1

        // Subtle top glow strip
        Rectangle {
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width - 2
            height: 4
            radius: 2
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: "#3c1a73e8" }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }

        // Layout chứa các thành phần theo chiều dọc
        Column {
            anchors.centerIn: parent
            spacing: 12

            // App Icon
            Image {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 120
                height: 120
                source: "../../assets/splash.png" // Đảm bảo đường dẫn này đúng cấu trúc thư mục của bạn
                fillMode: Image.PreserveAspectFit
            }

            // App Title
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "pyRoboCopy"
                font.family: "Segoe UI"
                font.pixelSize: 24
                font.bold: true
                color: "#e0e0e0"
            }

            // Tagline
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Fast parallel file transfer"
                font.family: "Segoe UI"
                font.pixelSize: 12
                color: "#666666"
            }
            
            // Spacer
            Item { 
                width: 1
                height: 15 
            }

            // Progress Bar Track
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 400
                height: 8
                color: "#2a2a2a"
                radius: 4

                // Progress Bar Fill (Binding trực tiếp từ ViewModel Python)
                Rectangle {
                    height: parent.height
                    width: vm ? (parent.width * (vm.progress / 100)) : 0
                    radius: 4
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: "#1a73e8" }
                        GradientStop { position: 1.0; color: "#34a853" }
                    }
                    
                    Behavior on width {
                        NumberAnimation { duration: 50 }
                    }
                }
            }

            // Status Text (Binding từ vm.status)
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: vm ? vm.status : "Loading…"
                font.family: "Segoe UI"
                font.pixelSize: 11
                color: "#555555"
            }
        }

        // Version / Copyright
        Text {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 14
            anchors.horizontalCenter: parent.horizontalCenter
            text: "v0.2.0"
            font.family: "Segoe UI"
            font.pixelSize: 11
            color: "#3a3a3a"
        }
    }
}
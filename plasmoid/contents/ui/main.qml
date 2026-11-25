import QtQuick 2.15
import QtQuick.Layouts 1.15
import org.kde.plasma.plasmoid 2.0
import org.kde.plasma.core 2.0 as PlasmaCore
// Components 2 only for the menu: its Menu is a real QMenu window, while a Components 3 popup
// would be clipped to the panel.
import org.kde.plasma.components 2.0 as PC2
import org.kde.plasma.components 3.0 as PC3

Item {
    id: root

    readonly property string usagePageUrl: "https://claude.ai/settings/usage"
    readonly property int pollIntervalMs: 60 * 1000
    readonly property int warningPercent: 20
    readonly property int criticalPercent: 10
    readonly property var limitWindows: [
        { name: "five_hour", label: i18nc("short label of the 5-hour limit window", "5h") },
        { name: "seven_day", label: i18nc("short label of the weekly limit window", "wk") },
    ]

    property var usage: ({})
    property bool busy: false
    readonly property bool hasData: usage.remainingPercent !== undefined
    readonly property string level: !hasData ? "normal"
        : usage.remainingPercent <= criticalPercent ? "critical"
        : usage.remainingPercent <= warningPercent ? "warning"
        : "normal"

    // Set once the actions exist; the click menu binds to them so both menus share text and icons.
    property QtObject refreshAction: null
    property QtObject openUsagePageAction: null

    Plasmoid.preferredRepresentation: Plasmoid.compactRepresentation
    Plasmoid.toolTipMainText: usage.error ? i18n("Claude limit unavailable") : i18n("Claude limit")
    Plasmoid.toolTipSubText: hasData ? detailsText()
        : usage.error ? errorText()
        : i18n("Updating…")

    Plasmoid.compactRepresentation: MouseArea {
        id: compact

        readonly property int iconSize: Math.min(height, PlasmaCore.Units.iconSizes.smallMedium)

        Layout.minimumWidth: row.implicitWidth
        Layout.preferredWidth: row.implicitWidth
        onClicked: menu.openRelative()

        RowLayout {
            id: row
            anchors.centerIn: parent
            spacing: PlasmaCore.Units.smallSpacing

            PlasmaCore.SvgItem {
                Layout.preferredWidth: compact.iconSize
                Layout.preferredHeight: compact.iconSize
                svg: PlasmaCore.Svg {
                    imagePath: Qt.resolvedUrl("../icons/claude.svg").toString().replace("file://", "")
                    colorGroup: PlasmaCore.ColorScope.colorGroup
                }
            }

            PC3.Label {
                text: root.hasData ? root.usage.remainingPercent + "%" : "—"
                color: root.level === "critical" ? PlasmaCore.ColorScope.negativeTextColor
                    : root.level === "warning" ? PlasmaCore.ColorScope.neutralTextColor
                    : PlasmaCore.ColorScope.textColor
            }
        }

        PC2.Menu {
            id: menu
            visualParent: compact
            placement: root.menuPlacement()

            PC2.MenuItem { action: root.refreshAction }
            PC2.MenuItem { action: root.openUsagePageAction }
        }
    }

    PlasmaCore.DataSource {
        id: runner
        engine: "executable"
        onNewData: function (sourceName, data) {
            disconnectSource(sourceName)
            root.busy = false
            root.usage = root.parseOutput(data.stdout)
        }
    }

    Timer {
        interval: root.pollIntervalMs
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    Component.onCompleted: {
        plasmoid.setAction("refresh", i18n("Refresh"), "view-refresh")
        plasmoid.setAction("openUsagePage", i18n("Open usage page"), "internet-web-browser")
        refreshAction = plasmoid.action("refresh")
        openUsagePageAction = plasmoid.action("openUsagePage")
    }

    function action_refresh() {
        refresh()
    }

    function action_openUsagePage() {
        Qt.openUrlExternally(usagePageUrl)
    }

    function refresh() {
        if (busy)
            return
        busy = true
        runner.connectSource("claude-usage")
    }

    function parseOutput(stdout) {
        try {
            return JSON.parse(stdout)
        } catch (e) {
            return { error: "no_output" }
        }
    }

    function detailsText() {
        var lines = []
        limitWindows.forEach(function (window) {
            var data = usage.windows[window.name]
            if (!data)
                return
            lines.push(data.resetsAt
                ? i18n("%1: %2%, resets %3", window.label, data.remainingPercent, resetMoment(data.resetsAt))
                : i18n("%1: %2%", window.label, data.remainingPercent))
        })
        if (usage.recordedAt)
            lines.push(i18n("Data from %1", dataMoment(usage.recordedAt)))
        return lines.join("\n")
    }

    function resetMoment(epochSeconds) {
        var date = new Date(epochSeconds * 1000)
        return isToday(date) ? i18n("today at %1", clock(date)) : dayAndClock(date)
    }

    function dataMoment(epochSeconds) {
        var date = new Date(epochSeconds * 1000)
        return isToday(date) ? clock(date) : dayAndClock(date)
    }

    function isToday(date) {
        return date.toDateString() === new Date().toDateString()
    }

    function clock(date) {
        return date.toLocaleTimeString(Qt.locale(), "HH:mm")
    }

    function dayAndClock(date) {
        return date.toLocaleString(Qt.locale(), i18nc("Qt date format of a day other than today", "ddd, MMM d 'at' HH:mm"))
    }

    function errorText() {
        switch (usage.error) {
        case "not_set_up": return i18n("No data: set claude-usage record as the Claude Code status line")
        case "no_limits": return i18n("Claude Code has not reported limits yet")
        default: return i18n("claude-usage gave no answer")
        }
    }

    function menuPlacement() {
        switch (plasmoid.location) {
        case PlasmaCore.Types.TopEdge: return PlasmaCore.Types.BottomPosedLeftAlignedPopup
        case PlasmaCore.Types.LeftEdge: return PlasmaCore.Types.RightPosedTopAlignedPopup
        case PlasmaCore.Types.RightEdge: return PlasmaCore.Types.LeftPosedTopAlignedPopup
        default: return PlasmaCore.Types.TopPosedLeftAlignedPopup
        }
    }
}

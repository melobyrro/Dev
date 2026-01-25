# Wyze Cameras - Requirements Document

**Version**: 1.1 (Updated to Actual)
**Last Updated**: 2026-01-23
**Dashboard Source**: `wyze/dashboard-iteration-20260120-2246.yaml`

---

## 1. Dashboard Design (Actual)

The dashboard uses a 2-column grid layout focused on live feeds and event snapshots.

### 1.1 Live Feeds
- **Cameras**:
  - Front Door
  - Living Room
  - Patio
  - Baby Room
- **Format**: `picture-glance` cards with RTSP streams.
- **Controls**: PTZ controls (where supported/configured), Sound toggle.

### 1.2 Event Snapshots
- **Mechanism**: Displays the latest image captured by motion events.
- **Entities**: `camera.wyze_*_snapshot` (or equivalent).

---

## 2. Automation & Logic Requirements

- **Stream Handling**: Relies on `go2rtc` or similar bridge (implied by `rtsp` references in config).
- **Motion Detection**: Binary sensors `binary_sensor.wyze_*_motion` trigger snapshots/recording.

---

## 3. Configuration Management

| File | Purpose | Location |
|------|---------|----------|
| `dashboard-iteration-20260120-2246.yaml` | Current Dashboard Layout | `wyze/` |
| `configuration.yaml` | RTSP Stream Config | `ha-config/` |

---

## 4. Future Enhancements

- **Object Detection**: Integrate Frigate or similar for Person/Pet detection events.
- **Notification**: Rich notifications with snapshots when motion is detected while "Armed".
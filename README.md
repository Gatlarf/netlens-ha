<p align="center"><img src="images/logo.png" alt="Netlens" width="360"></p>

# Netlens for Home Assistant

A [Home Assistant](https://www.home-assistant.io/) integration for **[Netlens](https://github.com/Gatlarf/netlens)**, a self-hosted LAN scanner and network map. It brings Netlens' statistics and device presence into Home Assistant:

- **Network statistics** as sensors: devices, online, offline, new devices, network uptime, open ports, events, last scan time/duration/hosts.
- **Health**: a *Problem* sensor that turns on when the last scan failed, no scan finished for 3 hours, or a Netlens plugin (router/hypervisor connector) is failing; a *Scan running* sensor.
- **Areas:** a tracked device gets its Netlens group (room, floor...) as its suggested area.
- **Presence for the devices you choose**: one `connectivity` binary sensor per device, grouped as Home Assistant devices that **mirror the Netlens hierarchy** (a laptop below its mesh node, below the router).
- **Events** for automations: new device, device offline/online, port opened, IP changed.

It only reads from Netlens (one request per minute for everything) and never changes anything.

> Status: early release. Entities and options may still change.

## Requirements

- Netlens **0.2.38 or newer** (the Wi-Fi, unknown-device, service, flapping, backup, identification, DHCP and passive-listening sensors need the Netlens that has those features and show *unknown* with an older one) (it needs the statistics API, `GET /api/stats/summary`).
- Home Assistant **2024.12 or newer**.
- Home Assistant must be able to reach Netlens (default `http://<host>:8080`) and you need an **API token** from Netlens (*Settings → Users & tokens*; a read-only viewer user is enough) or, on older installs, the `NETLENS_TOKEN` access token.

## Installation

### With HACS (recommended)

1. In HACS open the menu (three dots) → **Custom repositories**.
2. Add `https://github.com/Gatlarf/netlens-ha` with category **Integration**.
3. Search for **Netlens** in HACS, download it, and **restart Home Assistant**.

### Manually

Copy the folder `custom_components/netlens` of this repository into the `custom_components` folder of your Home Assistant configuration and restart.

## Setup

**Settings → Devices & services → Add integration → Netlens**, then enter:

| Field | Meaning |
|---|---|
| Netlens URL | for example `http://192.168.0.189:8080` (without `http://` it is added) |
| Access token | an **API token of a read-only viewer user** (Netlens 0.2.50 and later; recommended), or the `NETLENS_TOKEN` of an older install: create the user and token under *Settings → Users & tokens* in Netlens, so Home Assistant can look but never change anything |
| Verify the TLS certificate | only matters for `https` (for example behind a reverse proxy with a self-signed certificate) |

If Netlens later refuses the token, Home Assistant asks for a new one (re-authentication). To change the token or the address on purpose, open the integration (Settings → Devices & services → Netlens), the three-dot menu of the entry, and choose **Reconfigure**: leave the token empty to keep the current one. Entities, names and automations stay.

### Options

Open the integration → **Configure**:

| Option | Meaning |
|---|---|
| Poll interval | 30 to 3600 seconds (default 60) |
| Fire events | turn the Home Assistant events below on or off (default on) |
| Skip maintenance events | do not fire events that Netlens held back because the device was inside a maintenance window (default on). The event data still carries `maintenance` when you turn this off |
| Devices to track | the Netlens devices that get their own presence sensor and device. **None by default**, because a network can have dozens of devices |

Untracking a device removes its sensor and device again.

## Entities

All of these belong to the **Netlens** device.

| Entity | Notes |
|---|---|
| Devices, Devices online, Devices offline, Unknown devices | counts (*unknown* = not marked as known in Netlens) |
| New devices (24 h) | devices first seen in the last day |
| Network uptime (24 h) | share of successful checks over all devices, in % |
| Open ports | open ports found on all devices |
| Events (24 h) | events Netlens logged in the last day |
| Last scan | timestamp (device class *timestamp*) |
| Last scan duration, Last scan hosts found | of the most recent finished scan |
| Wi-Fi clients, Weak Wi-Fi clients | from a router plugin in Netlens (weak = signal below -75 dBm) |
| Service checks down | checks of the Netlens *Services* page that are down |
| Plugin updates available | installed Netlens plugins that have a newer release in the plugin index |
| Flapping devices | devices that changed between online and offline at least 6 times in the last 24 hours (Netlens' *Stability* card investigates why) |
| Last backup | timestamp of the last scheduled Netlens backup (*unknown* until one has run) |
| Problems, Version | diagnostic |
| Problem | binary sensor (*problem*); attributes list the failing plugins and the scan failures of the last 24 h |
| Scan running | binary sensor (*running*) |
| Backup problem | binary sensor (*problem*, diagnostic): on when the last scheduled backup failed; the *Problem* sensor counts it too (attribute `backup_failed`) |
| *Reverse proxy sites down*, *Certificates expiring soon*, *Days until the next certificate ends*, and the *Certificate problem* binary sensor (on when a certificate ends within 14 days) | from the reverse proxy plugins of Netlens 0.3.119 and later (Nginx Proxy Manager); enabled from the start when Netlens has sites, otherwise disabled |
| *Always-on devices uptime (24 h)*, *Always-on devices online* (and, disabled by default, *Always-on devices uptime (7 days)*) | the availability of the devices you marked as always-on in Netlens (0.3.162 and later), apart from phones and tablets that come and go; enabled from the start once at least one device is marked |
| *Internet download speed*, *Internet upload speed*, *Internet ping* (and, disabled by default, *Internet jitter* and *Last internet speed test*) | from the speed tests of Netlens 0.3.154 and later (Network → Speed tests); the sensors hold the result of the latest internet test, so switch on the scheduled test in Netlens (every 1 to 24 hours) to keep them current; enabled from the start once Netlens has an internet test result, otherwise disabled |
| *Devices with a health warning*, *Devices with a critical health reading*, *Days until the first disk is full*, and the *Health problem* binary sensor (on when a reading is past a limit or a disk will be full within 14 days) (and, disabled by default, *Devices with health monitoring*, *Devices whose health cannot be read*) | from the health monitoring of Netlens 0.4 and later (a device page → Health → Set up health monitoring); enabled from the start once Netlens monitors a device |
| *Remote sites not reporting*, *Remote site problems*, and the *Remote site problem* binary sensor (and, disabled by default, *Remote sites*) | from the remote sites of Netlens 0.4 and later (Monitoring → Remote sites); enabled from the start once there is a site |
| *Reverse proxy sites*, *Sites without a device*, *Containers with a newer image* (the Docker plugin's *Check for newer images*), *Devices not seen for 30 days*, *Network uptime (7 days)*, *Time since last good scan*, *Average Wi-Fi signal*, *Service checks*, *Devices of unknown type*, *Devices with a private address*, *DHCP servers*, *DNS records to write*, *DNS conflicts* (the DNS registration of Netlens), *Containers running*, *Unhealthy containers*, *Restarting containers*, *Guests running*, *Guest updates available* (from the Proxmox, TrueNAS and Docker plugins), *Passive listening* (binary sensor: Netlens is listening to DHCP / mDNS / UPnP announcements) | disabled by default; enable them in the entity list |

For each **tracked device** that has health monitoring in Netlens 0.4 or later there are also *Health* (ok, warning, critical), *Processor*, *Memory in use*, *Fullest disk*, *Temperature* and *UPS battery* sensors, as far as the device reports them.

For each **tracked device**: a binary sensor named after the device (*connectivity*: on = online). Attributes: `ip`, `mac`, `vendor`, `type`, `parent_name`, `last_seen`, `trusted`. The Home Assistant device carries the vendor, type and MAC address, links to the device page in Netlens, and sits below its parent when the parent is tracked as well (otherwise below the Netlens hub). Renames in Netlens are followed. A device deleted in Netlens becomes *unavailable*.

**Update entity** (`update.netlens_update`): *on* when a newer Netlens has been published; its release link opens the changelog. It cannot install the update (update your container as described in the Netlens README), but it works with Home Assistant's update notifications and automations.

## Events

When *Fire events* is on, new entries of the Netlens event log are fired on the Home Assistant bus (the first poll after a restart only remembers where it is, so old events are not replayed):

| Event | When |
|---|---|
| `netlens_new_device` | a device was seen for the first time |
| `netlens_device_offline` / `netlens_device_online` | a device went offline / came back |
| `netlens_port_opened` | a new open port appeared on a device |
| `netlens_service_down` / `netlens_service_up` | a service check of Netlens went down / recovered (`detail` says which) |
| `netlens_port_unexpected` | a port outside the device's baseline opened (Netlens 0.2.50 and later) |
| `netlens_port_missing` | a port from the device's baseline is gone |
| `netlens_port_closed` | a port closed on a device without a baseline |
| `netlens_dhcp_rogue` | a new, untrusted DHCP server answered on the network (Netlens 0.2.60 and later) |
| `netlens_gateway_changed` | the MAC address behind the gateway changed (possible ARP spoofing or a replaced router) |
| `netlens_backup_failed` | a scheduled Netlens backup failed (`detail` says why) |
| `netlens_wifi_roamed` | a Wi-Fi device moved to another mesh node |
| `netlens_ip_reused` | an IP address was taken over by another device |
| `netlens_ip_changed` | a device changed its IP address |
| `netlens_certificate_expiring` | a certificate used by a reverse proxy site ends soon, or has ended (Netlens 0.3.116 and later; `detail` names it) |
| `netlens_update_available` | an app, or the image of a container, has an update (the container check needs Netlens 0.3.119 and later) |
| `netlens_container_unhealthy` / `netlens_container_restarting` / `netlens_container_stopped` | a container's health check fails / it keeps restarting / it stopped with an error |
| `netlens_login_failed` | someone keeps entering a wrong password or token (Netlens 0.3.128 and later; `detail` names the address): a possible attack on a Netlens that is reachable from the internet |
| `netlens_guest_stopped` / `netlens_guest_started` | a virtual machine, LXC container or app stopped / started |

Event data: `entry_id`, `event_id`, `time`, `detail`, `maintenance`, `device_id`, `device_name`, `ip`, `mac`.

### Example automations

Notify when something new joins the network:

```yaml
automation:
  - alias: "Unknown device on the network"
    trigger:
      - platform: event
        event_type: netlens_new_device
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "New device on the network"
          message: "{{ trigger.event.data.device_name }} ({{ trigger.event.data.ip }}) {{ trigger.event.data.detail }}"
```

Warn when Netlens reports a problem for more than 10 minutes:

```yaml
automation:
  - alias: "Netlens problem"
    trigger:
      - platform: state
        entity_id: binary_sensor.netlens_problem
        to: "on"
        for: "00:10:00"
    action:
      - service: persistent_notification.create
        data:
          title: "Netlens"
          message: "{{ state_attr('binary_sensor.netlens_problem', 'failing_plugins') }}"
```

### Example dashboard card

```yaml
type: entities
title: Network
entities:
  - sensor.netlens_devices_online
  - sensor.netlens_devices_offline
  - sensor.netlens_network_uptime_24_h
  - sensor.netlens_last_scan
  - binary_sensor.netlens_problem
```

(Entity ids depend on your language and names; check **Settings → Entities**.)

## Troubleshooting

| Message | What to do |
|---|---|
| *Cannot reach Netlens at that address* | Check the URL and port, and that Home Assistant can reach that host (Docker networks, firewall). |
| *Netlens refused the token* | Create a new API token under *Settings → Users & tokens* in Netlens (or use the `NETLENS_TOKEN` of an older install), then use the entry's **Reconfigure** or **Re-authenticate**. |
| *This Netlens is too old, or newer than this integration understands* | Update Netlens to 0.2.38 or newer, or update this integration. |
| Entities show *unavailable* | Netlens did not answer; the log of the integration says why. They recover by themselves. |

Download **diagnostics** from the integration page when reporting a problem (the token, addresses, MACs and device names are redacted).

## Security

The token is stored by Home Assistant like any other integration credential. The integration only uses read-only endpoints. Netlens speaks plain HTTP by default, so use it on a trusted network, or put a TLS reverse proxy in front.

## Development

```
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

The tests run against a fake Netlens API with the Home Assistant test harness (`pytest-homeassistant-custom-component`). The integration needs these Netlens endpoints: `GET /api/stats/summary` (versioned: `api` must be `1`) and `GET /api/events?since_id=`.

## License

MIT, see `LICENSE`.

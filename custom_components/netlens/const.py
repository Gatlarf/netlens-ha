"""Constants for the Netlens integration."""

DOMAIN = "netlens"

CONF_URL = "url"
CONF_TOKEN = "token"
CONF_VERIFY_SSL = "verify_ssl"

CONF_SCAN_INTERVAL = "scan_interval"  # seconds between polls (options)
CONF_TRACK_EVENTS = "track_events"  # fire Home Assistant events for what Netlens logs (options)
CONF_SKIP_MAINTENANCE = "skip_maintenance"  # ignore events Netlens held back during a maintenance window (options)
CONF_DEVICES = "devices"  # keys of the devices that get their own entities (options)

DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 3600

SUPPORTED_API = 1  # version of /api/stats/summary this integration understands

# Netlens event kind -> Home Assistant bus event
EVENT_MAP = {
    "device_new": "netlens_new_device",
    "device_offline": "netlens_device_offline",
    "device_online": "netlens_device_online",
    "port_opened": "netlens_port_opened",
    "ip_changed": "netlens_ip_changed",
    "ip_reused": "netlens_ip_reused",
    "service_down": "netlens_service_down",
    "service_up": "netlens_service_up",
    "wifi_roamed": "netlens_wifi_roamed",
    "port_unexpected": "netlens_port_unexpected",
    "port_missing": "netlens_port_missing",
    "port_closed": "netlens_port_closed",
    "backup_failed": "netlens_backup_failed",
    "dhcp_rogue": "netlens_dhcp_rogue",
    "gateway_changed": "netlens_gateway_changed",
    "cert_expiring": "netlens_certificate_expiring",
    "guest_update_available": "netlens_update_available",
    "container_unhealthy": "netlens_container_unhealthy",
    "container_restarting": "netlens_container_restarting",
    "container_stopped": "netlens_container_stopped",
    "guest_stopped": "netlens_guest_stopped",
    "guest_started": "netlens_guest_started",
}

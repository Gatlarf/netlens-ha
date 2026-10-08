"""Constants for the Netlens integration."""

DOMAIN = "netlens"

CONF_URL = "url"
CONF_TOKEN = "token"
CONF_VERIFY_SSL = "verify_ssl"

CONF_SCAN_INTERVAL = "scan_interval"  # seconds between polls (options)
CONF_TRACK_EVENTS = "track_events"  # fire Home Assistant events for what Netlens logs (options)
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
}

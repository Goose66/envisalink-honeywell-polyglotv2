## EnvisaLink DSC Nodeserver Configuration
### Advanced Configuration:
- key: shortPoll, value: polling interval for connection status of Envisalink and zone timers (defaults to 30 seconds)
- key: longPoll, value: interval for watchdog timer resets if watchdog timer is disabled (see below, defaults to 600 seconds)

NOTE: The alarm panel reports status changes immediately and has a 4 minute keep alive broadcast, so frequent polling for state in shortpoll is not required. longpoll needs to be less than 20 minutes to prevent EnvisaLink from rebooting.

### Custom Configuration Parameters:

#### Required:
- key: ipaddress, value: locally accessible hostname or IP address of EnvisaLink EVL-3/4 (e.g., "192.168.1.145")
- key: password, value: password for EnvisaLink device
- key: usercode, value: user code for disarming alarm panel

#### Optional:
- key: numpartitions, value: number of partition nodes to generate (defaults to 1)
- key: numzones, value: number of zone nodes to generate (defaults to 8)
- key: disablewatchdog, value: 0 or 1 for whether EyezOn cloud service watchdog timer should be disabled (defaults to 0 - not disabled)
- key: zonetimerdumpflag, value: numeric flag indicating whether dumping of the zone timers should be done on shortpoll (1), longpoll (2), or disabled altogether (0) (defaults to 1 - shortpoll)
- key: smartzonetracking, value: 0 or 1 for whether nodeserver should use a heuristic to track zone status (open, closed) or just rely on EnvisaLink's zone status reporting (defaults to 0 - do not track)

NOTE: On nodeserver start, the child nodes for the Alarm Panel are created based on the numbers configured. The disablewatchdog should be enabled if the EnvisaLink is firewalled to prevent the EnvsiaLink from rebooting after 20 minutes.


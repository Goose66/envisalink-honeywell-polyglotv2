# envisalink-vista-polyglotv2
A Nodeserver for Polyglot v2 that interfaces with a Howeywell/Ademco Visata series alarm panel through an EnvisaLink EVL-3/4 adapater. See http://www.eyezon.com/?page_id=176 for more information on the EnvisaLink EVL-4.

Instructions for manual, co-resident installation:

1. Copy the files from this repository to the folder ~/.polyglot/nodeservers/EnvisaLink-HW in your Polyglot v2 installation.
2. Log into the Polyglot Version 2 Dashboard (https://(Polyglot IP address):3000)
3. Add the EnvisaLink-Vista nodeserver as a Local nodeserver type.
4. Add the following required Custom Configuration Parameters under Configuration:
```
    key: ipaddress, value: locally accessible IP address of EnvisaLink EVL-3/4 (e.g., "192.168.1.145")
    key: password, value: password for EnvisaLink device
    key: usercode, value: user code for disarming alarm panel
```
5. Add the following optional Custom Configuration Parameters:
```
    key: numpartitions, value: number of partition nodes to generate (defaults to 1)
    key: numzones, value: number of zone nodes to generate (defaults to 8)
    key: disablewatchdog, value: 0 or 1 for whether EyezOn cloud service watchdog timer should be disabled (defaults to 0 - not disabled)
    key: zonetimerdumpflag, value: numeric flag indicating whether dumping of the zone timers should be done on shortpoll (1), longpoll (2), or disabled altogether (0) (defaults to 1 - shortpoll)
```
The nodes of the EnvisaLink Nodeserver generate the following commands in the ISY, allowing the nodes to be added as controllers to scenes:

ZONE
- Sends a *DON* command when the zone is opened (not working)
- Sends a *DOF* command when the zone is closed (not working)

PARTITION
- Sends a *DON* command when the partition is alarming
- Sends a *DOF* command when the partition is disarmed

CONTROLLER
- Sends a *AWAKE* command periodically for heartbeat monitoring (not working)

Here are some things to know about this version: (these mostly have to do with the DSC version of the nodeserver)

1. This is a prelease version - many things do not work.
2. Zone states are not working (at least for my test panel)
3. Initially, there are several state values that are unknown when the nodeserver starts and will default to 0 (or last known value if restarted). This includes trouble states, door chime, and the like. These state values may not be correct until the status is changed while the nodeserver is running.
4. The connection to the EnvisaLink and alarm panel is not made until the first short poll (e.g., 30 seconds after start). The various state values (zone states, zone bypass, zone timers, etc.) are updated over subsequent short polls. Therefore, depending on the "shortPoll" configuration setting and the number of partitions, it may take a few minutes after starting the nodeserver for all the states to be updated.
5. If your EnvisaLink is firewalled and can not connect to the EyezOn web service, then the EnvisaLink will reboot every 20 minutes ("Watchdog Timer") in order to try and reestablish the connection to the web service. This will kill the connection to the nodeserver as well and it will (attempt to) reconnect on the next short poll. If you set the "diablewatchdog" configuration setting to 1, the nodeserver will send a periodic poll to the EnvisaLink to reset the Watchdog Timer so that the EnvisaLink won't reboot. The poll is sent every long poll if the "diablewatchdog" configuration parameter is set, so the "longpoll" configuration setting needs to be less than 1200 seconds (20 minutes).
6. The zone timers ("Time Closed") represent the time since the last closing of the zone, in seconds, and are calculated in 5 second intervals. The timers have a maximum value of 327675 seconds (91 hours) and won't count up beyond that. The zone timers are dumped with every short poll.  

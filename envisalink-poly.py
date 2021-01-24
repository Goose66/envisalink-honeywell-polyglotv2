#!/usr/bin/python3
# Polyglot Node Server for EnvisaLink EVL 3/4 Device (DSC)

import sys
import envisalinktpi as EVL
import polyinterface

# TODO: Test Fire zone and reporitng functionality
# TODO: Add Zone Bypass command (knowing which partition is challenge) and driver (clearing is the challenge)
# TODO: Add detection of Alarming status for zones
# TODO: Add heartbeat from nodeserver
# TODO: Add shortcut arming (with #)
# TODO: Process CID events for more information

# contstants for ISY Nodeserver interface
_ISY_BOOL_UOM = 2 # Used for reporting status values for Controller node
_ISY_INDEX_UOM = 25 # Index UOM for custom states (must match editor/NLS in profile):
_ISY_USER_NUM_UOM = 70 # User Number UOM for reporting last user number
_ISY_SECONDS_UOM = 58 # used for reporting duration in seconds

_LOGGER = polyinterface.LOGGER

_PART_ADDR_FORMAT_STRING = "partition%1d"
_ZONE_ADDR_FORMAT_STRING = "zone%02d"

_PARM_IP_ADDRESS_NAME = "ipaddress"
_PARM_PASSWORD_NAME = "password"
_PARM_USER_CODE_NAME = "usercode"
_PARM_NUM_PARTITIONS_NAME = "numpartitions"
_PARM_NUM_ZONES_NAME = "numzones"
_PARM_DISABLE_WATCHDOG_TIMER = "disablewatchdog"

_DEFAULT_IP_ADDRESS = "0.0.0.0"
_DEFAULT_PASSWORD = "user"
_DEFAULT_USER_CODE = "5555"
_DEFAULT_NUM_PARTITIONS = 1
_DEFAULT_NUM_ZONES = 8

# values for zonetimerdumpflag in custom configuration'
_PARM_ZONE_TIMER_DUMP_FLAG = "zonetimerdumpflag"
_ZONE_TIMER_DUMP_DISABLED = 0
_ZONE_TIMER_DUMP_SHORTPOLL = 1
_ZONE_TIMER_DUMP_LONGPOLL = 2
_DEFAULT_ZONE_TIMER_DUMP_FLAG = _ZONE_TIMER_DUMP_SHORTPOLL

# constants from nodeserver profile
_IX_PARTITION_STATE_READY = 0
_IX_PARTITION_STATE_NOT_READY = 1
_IX_PARTITION_STATE_ARMED_AWAY = 2
_IX_PARTITION_STATE_ARMED_STAY = 3
_IX_PARTITION_STATE_ARMED_AWAY_ZE = 4
_IX_PARTITION_STATE_ARMED_STAY_ZE = 5
_IX_PARTITION_STATE_ALARMING = 6
_IX_PARTITION_STATE_DELAY_EXIT = 7
_IX_PARTITION_STATE_ALARM_IN_MEMORY = 8

_IX_ZONE_STATE_CLOSED = 0
_IX_ZONE_STATE_OPEN = 1
_IX_ZONE_STATE_ALARMING = 2

# Node class for partitions
class Partition(polyinterface.Node):

    id = "PARTITION"

    # Override init to handle partition number
    def __init__(self, controller, primary, partNum):
        super(Partition, self).__init__(controller, primary, _PART_ADDR_FORMAT_STRING % partNum, "Partition %1d" % partNum)
        self.partitionNum = partNum
        self.initialBypassZoneDump = False
        self.readyState = False
        self.alarming = False

    # Update the driver values based on the command received from the EnvisaLink for the partition
    def set_state(self, state):
        
        if state == EVL.PARTITION_STATE_ALARMING:
    
            # send a DON commmand when the partition goes to an alarming state
            self.reportCmd("DON")
            self.alarming = True

            # set the status to Alarming
            self.setDriver("ST", _IX_PARTITION_STATE_ALARMING)

            self.readyState = False

            return

        else:

            # if partition was previously set to an alarming state, clear the state
            if self.alarming:

                # send a DOF commmand when the partition goes to an alarming state
                self.reportCmd("DOF")
                self.alarming = False

        if state in (EVL.PARTITION_STATE_READY, EVL.PARTITION_STATE_READY_ZONES_BYPASSED):

            self.setDriver("ST", _IX_PARTITION_STATE_READY) # Ready
            self.readyState = True
      
        else:

            if state == EVL.PARTITION_STATE_NOT_READY:
                self.setDriver("ST", _IX_PARTITION_STATE_NOT_READY) # Not Ready

            elif state == EVL.PARTITION_STATE_ARMED_STAY:
                self.setDriver("ST", _IX_PARTITION_STATE_ARMED_STAY)

            elif state == EVL.PARTITION_STATE_ARMED_AWAY:
                self.setDriver("ST", _IX_PARTITION_STATE_ARMED_AWAY)

            elif state == EVL.PARTITION_STATE_ARMED_STAY_ZE:
                self.setDriver("ST", _IX_PARTITION_STATE_ARMED_STAY_ZE)

            elif state == EVL.PARTITION_STATE_ARMED_AWAY_ZE:            
                self.setDriver("ST", _IX_PARTITION_STATE_ARMED_AWAY_ZE)

            elif state == EVL.PARTITION_STATE_EXIT_DELAY:
                self.setDriver("ST", _IX_PARTITION_STATE_DELAY_EXIT) 

            elif state == EVL.PARTITION_STATE_ALARM_IN_MEMORY:
                self.setDriver("ST", _IX_PARTITION_STATE_ALARM_IN_MEMORY)

            self.readyState = False
  
    # Arm the partition in Away mode (the listener thread will update the corresponding driver values)
    def arm_away(self, command):

        _LOGGER.info("Arming partition %d in away mode in arm_away()...", self.partitionNum)

        # send keys to arm away 
        if self.controller.envisalink.sendKeys(self.partitionNum, EVL.KEYS_ARM_AWAY.format(code=self.controller.userCode)):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to arm partition failed for node %s.", self.address)

    # Arm the partition in Stay mode (the listener thread will update the corresponding driver values)
    def arm_stay(self, command):

        _LOGGER.info("Arming partition %d in stay mode in arm_stay()...", self.partitionNum)
        
        # send keys to arm stay 
        if self.controller.envisalink.sendKeys(self.partitionNum, EVL.KEYS_ARM_STAY.format(code=self.controller.userCode)):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to arm partition failed for node %s.", self.address)

    # Arm the partition in Zero Entry mode (the listener thread will update the corresponding driver values)
    def arm_zero_entry(self, command):
        
        _LOGGER.info("Arming partition %d in zero_entry mode in arm_zero_entry()...", self.partitionNum)

        # send keys to arm instant 
        if self.controller.envisalink.sendKeys(self.partitionNum, EVL.KEYS_ARM_INSTANT.format(code=self.controller.userCode)):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to arm partition failed for node %s.", self.address)

    # Disarm the partition (the listener thread will update the corresponding driver values)
    def disarm(self, command):
        
        _LOGGER.info("Disarming partition %d in disarm()...", self.partitionNum)

        # send keys to disarm
        if self.controller.envisalink.sendKeys(self.partitionNum, EVL.KEYS_DISARM.format(code=self.controller.userCode)):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to disarm partition failed for node %s.", self.address)

    # Toggle the door chime for the partition (the listener thread will update the corresponding driver values)
    def toggle_chime(self, command):

        _LOGGER.info("Toggling door chime for partition %d in toggle_chime()...", self.partitionNum)

        # send door chime toggle keystrokes to EnvisaLink device for the partition numner
        if self.controller.envisalink.sendKeys(self.partitionNum, EVL.KEYS_TOGGLE_DOOR_CHIME.format(code=self.controller.userCode)):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to toggle door chime failed for node %s.", self.address)

    drivers = [
        {"driver": "ST", "value": 0, "uom": _ISY_INDEX_UOM},
        {"driver": "GV0", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV1", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV2", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV5", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV6", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV7", "value": 0, "uom": _ISY_BOOL_UOM},
    ]
    commands = {
        "DISARM": disarm,
        "ARM_AWAY": arm_away,
        "ARM_STAY": arm_stay,
        "ARM_ZEROENTRY": arm_zero_entry,
        "TOGGLE_CHIME": toggle_chime
    }

# Node class for zones
class Zone(polyinterface.Node):

    id = "ZONE"

    # Override init to handle partition number
    def __init__(self, controller, primary, zoneNum):
        super(Zone, self).__init__(controller, primary, _ZONE_ADDR_FORMAT_STRING % zoneNum, "Zone %02d" % zoneNum)
        self.zoneNum = zoneNum       

    # Set the zone state value
    def set_state(self, state):
        self.setDriver("ST", state)

    # Set the bypasse driver value
    def set_bypass(self, bypass):
        self.setDriver("GV0", bypass)

    # Set the zone timer driver value
    def set_timer(self, time):
        self.setDriver("GV1", time)
        
    drivers = [
        {"driver": "ST", "value": 0, "uom": _ISY_INDEX_UOM},
        {"driver": "GV1", "value": 327675, "uom": _ISY_SECONDS_UOM},
    ]
    commands = {}

# Node class for controller
class Controller(polyinterface.Controller):

    id = "CONTROLLER"

    def __init__(self, poly):
        super(Controller, self).__init__(poly)
        self.ip = ""
        self.password = ""
        self.name = "EnvisaLink-Vista Nodeserver"
        self.envisalink = None
        self.userCode = ""
        self.numPartitions = 0

    # Update the profile on the ISY
    def cmd_updateProfile(self, command):

        _LOGGER.info("Installing profile in cmd_updateProfile()...")
        
        self.poly.installprofile()
        
    # Update the profile on the ISY
    def cmd_setLogLevel(self, command):

        _LOGGER.info("Setting logging level in cmd_setLogLevel(): %s", str(command))

        # retrieve the parameter value for the command
        value = int(command.get("value"))
 
        # set the current logging level
        _LOGGER.setLevel(value)

        # store the new loger level in custom data
        self.addCustomData("loggerlevel", value)
        self.saveCustomData(self._customData)
        
        # update the state driver to the level set
        self.setDriver("GV20", value)
        
    def cmd_query(self):

        # Force EnvisaLink to report all statuses available for reporting

        # check for existing EnvisaLink connection
        if self.envisalink is None or not self.envisalink.connected():

            # Update the alarm panel connected status
            self.setDriver("GV1", 1, True, True)

            # send the status polling command to the EnvisaLink device
            # What can we send to the Honeywell panel to force reporting of statuses?
            #self.envisalink.sendCommand(EVL.CMD_STATUS_REPORT)

        else:

            # Update the alarm panel connected status
            self.setDriver("GV1", 0, True, True)

    # Start the nodeserver
    def start(self):

        _LOGGER.info("Starting envisaink Nodeserver...")

        # remove all notices from ISY Admin Console
        self.removeNoticesAll()

        # load custom data from polyglot
        self._customData = self.polyConfig["customData"]

        # If a logger level was stored for the controller, then use to set the logger level
        level = self.getCustomData("loggerlevel")
        if level is not None:
            _LOGGER.setLevel(int(level))
        
        # get custom configuration parameters
        configComplete = self.getCustomParams()

        # if the configuration is not complete, stop the nodeserver
        if not configComplete:
            self.poly.stop()
            return

        else:

            #  setup the nodes based on the counts of zones and partition in the configuration parameters
            self.build_nodes(self.numPartitions, self.numZones)

            # setting up the interface moved to shortpoll so that it is retried if initial attempt to connection fails
            # NOTE: this is for, e.g., startup after power failure where Polyglot may restart faster than network or
            # EnvisaLink

        # Set the nodeserver status flag to indicate nodeserver is running
        self.setDriver("ST", 1, True, True)

        # Report initial alarm panel connection status
        self.setDriver("GV1", 0, True, True)

        # Report the logger level to the ISY
        self.setDriver("GV20", _LOGGER.level, True, True)
                       
    # Called when the nodeserver is stopped
    def stop(self):
        
        # shudtown the connection to the EnvisaLink device
        if not self.envisalink is None:
            self.envisalink.shutdown()

            # Update the alarm panel connected status
            self.setDriver("GV1", 0, True, True)

        # Set the nodeserver status flag to indicate nodeserver is stopped
        # Note: this is currently not effective
        self.setDriver("ST", 0, True, True)
        
        
    # called every long_poll seconds
    def longPoll(self):

        # check for EVL connection
        if self.envisalink is not None and self.envisalink.connected():
        
            # if the EVL's watchdog timer is to be disabled, send a poll command to reset the timer
            # NOTE: this prevents the EnvisaLink from resetting the connection if it can't communicate with EyezON service
            if self.disableWDTimer:
                self.envisalink.sendCommand(EVL.CMD_POLL)

            # Check zone timer dump flag and force a zone timer dump
            if self.zoneTimerDumpFlag == _ZONE_TIMER_DUMP_LONGPOLL:
                self.envisalink.sendCommand(EVL.CMD_DUMP_ZONE_TIMERS)
    
    # called every short_poll seconds
    def shortPoll(self):

        # check for existing EnvisaLink connection
        if self.envisalink is None or not self.envisalink.connected():

            # Setup the interface to the EnvisaLink device and connect (starts the listener thread)
            self.envisalink = EVL.EnvisaLinkInterface(_LOGGER)
            
            _LOGGER.info("Establishing connection to EnvisaLink device...")

            if self.envisalink.connect(self.ip, self.password, self.process_command):

                # clear any prior connection failure notices
                self.removeNotice("no_connect")

                # set alarm panel connected status
                self.setDriver("GV1", 1, True, True)

            else:
                
                # set alarm panel connected status
                self.setDriver("GV1", 0, True, True)

                # Format errors
                _LOGGER.warning("Could not connect to EnvisaLink device at %s.", self.ip)
                self.addNotice({"no_connect": "Could not connect to EnvisaLink device. Please check the network and configuration parameters and restart the nodeserver."})
                self.envisalink = None              

        else:
            
            # Check zone timer dump flag and force a zone timer dump
            if self.zoneTimerDumpFlag == _ZONE_TIMER_DUMP_SHORTPOLL:
                self.envisalink.sendCommand(EVL.CMD_DUMP_ZONE_TIMERS)
             
             
    # Get custom configuration parameter values
    def getCustomParams(self):

        customParams = self.poly.config["customParams"] 
        complete = True

        # get IP address of the EnvisaLink device from custom parameters
        try:
            self.ip = customParams[_PARM_IP_ADDRESS_NAME]      
        except KeyError:
            _LOGGER.error("Missing IP address for EnvisaLink device in configuration.")

            # add a notification to the nodeserver's notification area in the Polyglot dashboard
            self.addNotice({"missing_ip": "Please update the '%s' parameter value in the nodeserver custom parameters and restart the nodeserver." % _PARM_IP_ADDRESS_NAME})

            # put a place holder parameter in the configuration with a default value
            customParams.update({_PARM_IP_ADDRESS_NAME: _DEFAULT_IP_ADDRESS})
            complete = False
            
        # get the password of the EnvisaLink device from custom parameters
        try:
            self.password = customParams[_PARM_PASSWORD_NAME]
        except KeyError:
            _LOGGER.error("Missing password for EnvisaLink device in configuration.")

            # add a notification to the nodeserver's notification area in the Polyglot dashboard
            self.addNotice({"missing_pwd": "Please update the '%s' parameter value in the nodeserver custom parameters and restart the nodeserver." % _PARM_PASSWORD_NAME})

            # put a place holder parameter in the configuration with a default value
            customParams.update({_PARM_PASSWORD_NAME: _DEFAULT_PASSWORD})
            complete = False

        # get the user code for the DSC panel from custom parameters
        try:
            self.userCode = customParams[_PARM_USER_CODE_NAME]
        except KeyError:
            _LOGGER.error("Missing user code for DSC panel in configuration.")

            # add a notification to the nodeserver's notification area in the Polyglot dashboard
            self.addNotice({"missing_code": "Please update the '%s' custom configuration parameter value in the nodeserver configuration and restart the nodeserver." % _PARM_USER_CODE_NAME})

            # put a place holder parameter in the configuration with a default value
            customParams.update({_PARM_USER_CODE_NAME: _DEFAULT_USER_CODE})
            complete = False

        # get the optional number of partitions, zones, and command outputs to create nodes for
        try:
            self.numPartitions = int(customParams[_PARM_NUM_PARTITIONS_NAME])
        except (KeyError, ValueError, TypeError):
            self.numPartitions = _DEFAULT_NUM_PARTITIONS

        try:
            self.numZones = int(customParams[_PARM_NUM_ZONES_NAME])
        except (KeyError, ValueError, TypeError):
            self.numZones = _DEFAULT_NUM_ZONES

        # get optional settings for watchdog timer
        try:
            self.disableWDTimer = (int(customParams[_PARM_DISABLE_WATCHDOG_TIMER]) == 1)
        except (KeyError, ValueError, TypeError):
            self.disableWDTimer = False
        
        # get optional settings for zone timer dump frequency
        try:
            self.zoneTimerDumpFlag = int(customParams[_PARM_ZONE_TIMER_DUMP_FLAG])
        except (KeyError, ValueError, TypeError):
            self.zoneTimerDumpFlag = _DEFAULT_ZONE_TIMER_DUMP_FLAG

        self.poly.saveCustomParams(customParams)

        return complete

    # Create nodes for zones, partitions, and command outputs as specified by the parameters
    def build_nodes(self, numPartitions, numZones):

        # create partition nodes for the number of partitions specified
        for i in range(0, numPartitions):
            
            # create a partition node and add it to the node list
            self.addNode(Partition(self, self.address, i+1))

        # create zone nodes for the number of partitions specified
        for i in range(0, numZones):
            
            # create a partition node and add it to the node list
            self.addNode(Zone(self, self.address, i+1))

    # Callback function for listener thread
    def process_command(self, cmd, data):

        # update the state values from the keypad updates
        # Note: This is rather chatty at one message every 4 seconds
        if cmd == EVL.CMD_KEYPAD_UPDATE:

            # parse the command parameters from the data
            # Partition, LED/Icon Bitfield, User/Zone, Beep, Alphanumeric
            parms = data.split(",")
            
            partNum = int(parms[0]) # Partition
            statusBits = int(parms[1], base=16) # LED/Icon Bitfield
            zoneNum = int(parms[2]) if parms[2].isdigit() else 0
            text1 = parms[4][:16] # First Alphanumeric Line
            text2 = parms[4][16:] # First Alphanumeric Line

            # if the report is not zone oriented, process status for the partition
            if (statusBits & EVL.LED_MASK_PARTITION_FLAG) > 0:

                # check if node for partition exists
                for addr in self.nodes:
                    if addr == _PART_ADDR_FORMAT_STRING % partNum:

                        partition = self.nodes[addr]

                        # update the partition state (ST driver)
                        # this is duplicate of statuses reported in CMD_PARTITION_STATE_CHANGE
                        # so whichever is the most reliable should be used
                        #partition.set_state(status byte from statusBits)

                        # update the partition flags from the status bits
                        partition.setDriver("GV0", int((statusBits & EVL.LED_MASK_CHIME) > 0)) # Chime
                        partition.setDriver("GV1", int((statusBits & EVL.LED_MASK_BYPASS) > 0)) # Zone Bypassed
                        partition.setDriver("GV2", int((statusBits & EVL.LED_MASK_ALARM_FIRE) > 0)) # Fire Alarm
                        partition.setDriver("GV5", int((statusBits & EVL.LED_MASK_LOW_BATTERY) > 0)) # Low Battery
                        partition.setDriver("GV6", int((statusBits & EVL.LED_MASK_AC_PRESENT) == 0)) # AC Trouble
                        partition.setDriver("GV7", int((statusBits & EVL.LED_MASK_SYS_TROUBLE) > 0)) # System Trouble

                        break

            # otherwise process zone based information
            else:
                # look at text1 to determine meaning of update, e.g. "BYPAS ZZ", "ALARM ZZ", "FAULT ZZ"
                pass

        # process the partition statuses on status change
        elif cmd == EVL.CMD_PARTITION_STATE_CHANGE:
                            
            # spilt the 16 characters of data into 8 individual 2-character hex strings 
            partStatuses = [data[i:i+2] for i in range(0, len(data), 2)]

            # iterate through the partitions nodes and update the state from the corresponding status value
            for addr in self.nodes:
                node = self.nodes[addr]
                if node.id == "PARTITION":
                    node.set_state(partStatuses[node.partitionNum - 1])

        # process the zone statuses on status change
        elif cmd == EVL.CMD_ZONE_STATE_CHANGE:

            # spilt the 16/32 characters of data into 8/16 individual 2-character hex strings
            zoneStateBytes = [data[i:i+2] for i in range(0, len(data), 2)]

            # convert the 2-character hex strings into a list of 64/128 integer zone states (0, 1)
            zoneStates = []
            for byte in zoneStateBytes:
                bits = int(byte, base=16)
                for i in range(8):
                    zoneStates.append(int((bits & (1 << i)) > 0))
                            
            # iterate through the zone nodes and set the state value the state list
            for addr in self.nodes:
                node = self.nodes[addr]
                if node.id == "ZONE":
                    node.set_state(zoneStates[node.zoneNum - 1])                   

        # if a CID event is sent, log it so that we can add functionality
        elif cmd == EVL.CMD_CID_EVENT:

            # parse the CID parameters from the data
            # QXXXPPZZZ0 where:
            #   Q = Qualifier. 1 = Event, 3 = Restoral
            #   XXX = 3 digit CID code
            #   PP = 2 digit Partition
            #   ZZZ = Zone or User (depends on CID code)
            #   0 = Always 0 (padding)
            isRestoral = (data[0:1] == "3") # Qaulifier
            code = int(data[1:4]) # CID code
            partNum = int(data[4:6]) # Partition
            zoneNum = int(data[6:9]) # Zone/User Num

            # log the CID code for testing
            _LOGGER.info("CID event received from Alarm Panel. Code: %d, Qualifier: %s, Partition: %d, Zone/User: %d", code, data[0:1], partNum, zoneNum)

        # handle zone timer dump
        elif cmd == EVL.CMD_ZONE_TIMER_DUMP:
            
            # spilt the 256/512 bytes of data into 64/128 individual 4-byte hex values 
            zoneTimerHexValues = [data[i:i+4] for i in range(0, len(data), 4)]

            # convert the 4-byte hex values to a list of integer zone timers
            # Note: Each 4-byte hex value is a little-endian countdown of 5-second
            # intervals, i.e. FFFF = 0, FEFF = 5, FDFF = 10, etc.  
            zoneTimers = []
            for leHexString in zoneTimerHexValues:
                beHexString = leHexString[2:] + leHexString[:2]
                time = (int(beHexString, base=16) ^ 0xFFFF) * 5
                zoneTimers.append(time)
                            
            # iterate through the zone nodes and set the time value from the bitfield
            for addr in self.nodes:
                node = self.nodes[addr]
                if node.id == "ZONE":
                    node.set_timer(zoneTimers[node.zoneNum - 1])
                    
        else:
            _LOGGER.info("Unhandled command received from EnvisaLink. Command: %s, Data: %s", cmd.decode("ascii"), data)

        # helper method for storing custom data
    def addCustomData(self, key, data):

        # add specififed data to custom data for specified key
        self._customData.update({key: data})

    # helper method for retrieve custom data
    def getCustomData(self, key):

        # return data from custom data for key
        return self._customData.get(key)

    drivers = [
        {"driver": "ST", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV1", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV20", "value": 0, "uom": _ISY_INDEX_UOM}
    ]

    commands = {
        "QUERY": cmd_query,
        "UPDATE_PROFILE" : cmd_updateProfile,
        "SET_LOGLEVEL": cmd_setLogLevel        
    }

# Main function to establish Polyglot connection
if __name__ == "__main__":
    try:
        poly = polyinterface.Interface()
        poly.start()
        controller = Controller(poly)
        controller.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)

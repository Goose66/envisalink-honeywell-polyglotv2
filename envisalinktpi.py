#!/usr/bin/python3
# Interface to EnvisaLink 3/4 TPI (Honeywell Vista)

import socket
import logging
import threading

# Pickup the root logger, and add a handler for module testing if none exists
_LOGGER = logging.getLogger()
if not _LOGGER.hasHandlers():
    logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', level=logging.DEBUG)

# Commands to control Honeywell Alarm Panel
CMD_POLL = b"00"
CMD_CHANGE_DEFAULT_PARTITION = b"01"
CMD_DUMP_ZONE_TIMERS = b"02"
CMD_KEYPRESS = b"03"

# Response commands sent by Vista alarm panel
# Note: have 0x80 added to them to differentiate them from control commands above (for processing command ACKs)
CMD_KEYPAD_UPDATE = b"80"
CMD_ZONE_STATE_CHANGE = b"81"
CMD_PARTITION_STATE_CHANGE = b"82"
CMD_CID_EVENT = b"83"
CMD_ZONE_TIMER_DUMP = b"FF" # actual code sent by panel

_CMD_RESPONSE_BASE = 0x80

# Keypad keystrokes for specific commands 
KEYS_DISARM = "{code}1"
KEYS_ARM_AWAY = "{code}2"
KEYS_ARM_STAY = "{code}3"
KEYS_ARM_INSTANT = "{code}7"
KEYS_TOGGLE_DOOR_CHIME = "{code}9"
KEYS_DUMP_BYPASS_ZONES = "{code}6*"
KEYS_DUMP_ZONE_FAULTS = "*"
KEYS_TOGGLE_ZONE_BYPASS = "{code}6{zone:2d}"

# Partition States
# Note: used to evaluate statuses returned in data from listener, so not byte strings
PARTITION_STATE_DOES_NOT_EXIST = "00"
PARTITION_STATE_READY = "01"
PARTITION_STATE_READY_ZONES_BYPASSED = "02"
PARTITION_STATE_NOT_READY = "03"
PARTITION_STATE_ARMED_STAY = "04"
PARTITION_STATE_ARMED_AWAY = "05"
PARTITION_STATE_ARMED_STAY_ZE = "06"
PARTITION_STATE_EXIT_DELAY = "07"
PARTITION_STATE_ALARMING = "08"
PARTITION_STATE_ALARM_IN_MEMORY = "09" 
PARTITION_STATE_ARMED_AWAY_ZE = "10"

LED_MASK_ARMED_STAY =       0b1000000000000000
LED_MASK_LOW_BATTERY =      0b0100000000000000
LED_MASK_FIRE =             0b0010000000000000
LED_MASK_READY =            0b0001000000000000
LED_MASK_PARTITION_FLAG =   0b0000100000000000 # Indicates is report is system or partition-oriented - not a zone oriented report. Not documented
LED_MASK_SYS_TROUBLE =      0b0000001000000000
LED_MASK_ALARM_FIRE =       0b0000000100000000
LED_MASK_ARMED_ZE =         0b0000000010000000
LED_MASK_CHIME =            0b0000000000100000
LED_MASK_BYPASS =           0b0000000000010000
LED_MASK_AC_PRESENT =       0b0000000000001000
LED_MASK_ARMED_AWAY =       0b0000000000000100
LED_MASK_ALARM_IN_MEMORY =  0b0000000000000010
LED_MASK_ALARMING =         0b0000000000000001

# Error codes returned in data for command acknowledgment
CMD_RESPONSE_CODE_OK = b"00"
_CMD_RESPONSE_CODES = {
    b"00": "No Error - Command Accepted",
    b"01": "Receive Buffer Overrun (a command is received while another is still being processed)",
    b"02": "Unknown Command",
    b"03": "Syntax Error",
    b"04": "Receive Buffer Overflow",
    b"05": "Receive State Machine Timeout (command not completed within 3 seconds)"
}

_EVL_TCP_PORT = 4025

_INITIAL_SOCKET_TIMEOUT = 0.5 # socket send/receive timeout for initial handshake (500ms)
_LISTENER_SOCKET_TIMEOUT = 20 # socket receive timeout for listener (20 seconds)

_EVL_LOGIN_PROMPT = b"Login:"
_EVL_LOGIN_SUCCESS = b"OK"
_EVL_LOGIN_FAILED = b"Failed"

_msgBuffer = bytearray()
_BUFFER_SIZE = 1024

class EnvisaLinkInterface(object):

    # Primary constructor method
    def __init__(self, logger=_LOGGER):

        # declare instance variables
        self._evlConnection = None
        self._listenerThread = None
        self._sendLock = threading.Lock()
        self._stopThread = False

        self._logger = logger

    # connect to specified EnvisaLink device
    def connect(self, deviceAddr, password, cmdCallback=None):

        self._logger.debug("Connecting to EnvisaLink device...")

        if self._connect_evl(deviceAddr, password):

            self._logger.info("Starting listener thread...")
            
            # setup thread for listener for commands from EnvisaLink with specified callback function
            self._listenerThread = threading.Thread(target=self._command_listener, args=(cmdCallback,))
            self._listenerThread.daemon = True
            try:
                self._listenerThread.start()
            except threading.ThreadError as e:
                self._logger.error("Error starting listener thread: %s", str(e))
                return False
            except:
                raise

            return True
        
        else:
            
            return False

    # connect socket to EnvisaLink and perform initial login handshake
    def _connect_evl(self, deviceAddr, password):

        # Open a socket for communication with the device at the specified address
        self._evlConnection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._evlConnection.settimeout(_INITIAL_SOCKET_TIMEOUT)
        try:
            self._evlConnection.connect((deviceAddr, _EVL_TCP_PORT))
        except (socket.error, socket.herror, socket.gaierror) as e:
            self._logger.error("Unable to establish connection with EnvisaLink device. Socket error: %s", str(e))
            self._evlConnection.close()
            return False
        except:
            raise
    
        # wait for login prompt from socket
        try:
            msg = self._evlConnection.recv(_BUFFER_SIZE)
        except socket.timeout:
            self._logger.error("No login prompt received from EnvisaLink after connection.")
            return False
        except socket.error as e:
            self._logger.error("Connection to EnvisaLink unexpectedly closed. Socket error: %s", str(e))
            self._evlConnection.close()
            return False
        except:
            raise

        # validate login prompt was received
        if len(msg) == 0:
            self._logger.error("Connection to EnvisaLink closed without receiving expected data.")
            self._evlConnection.close()
            return False

        elif msg.strip() != _EVL_LOGIN_PROMPT:
            self._logger.error("Invalid sequence received from EnvisaLink upon connection: %s", msg)
            self._evlConnection.close()
            return False

        # send device password
        try:
            self._evlConnection.sendall(password.encode("ascii") + b"\r\n")
        except socket.timeout:
            self._logger.error("Failure to send password to EnvisaLink - connection closed.")
            self._evlConnection.close()
            return False
        except socket.error as e:
            self._logger.error("Connection to EnvisaLink unexpectedly closed. Socket error: %s", str(e))
            self._evlConnection.close()
            return False
        except:
            raise
    
        # wait for login acknowledgement from socket
        try:
            msg = self._evlConnection.recv(_BUFFER_SIZE)
        except socket.timeout:
            self._logger.error("No ACK received from EnvisaLink after login.")
            return False
        except socket.error as e:
            self._logger.error("Connection to EnvisaLink unexpectedly closed. Socket error: %s", str(e))
            self._evlConnection.close()
            return False
        except:
            raise

        # validate login ACK
        if len(msg) == 0:
            self._logger.error("Connection to EnvisaLink closed without receiving expected data.")
            self._evlConnection.close()
            return False

        elif msg.strip() == _EVL_LOGIN_FAILED:
            self._logger.error("Invalid password specified. Login failed.")
            self._evlConnection.close()
            return False

        elif msg.strip() != _EVL_LOGIN_SUCCESS:
            self._logger.error("Invalid sequence received from EnvisaLink upon login: %s", msg)
            self._evlConnection.close()
            return False

        # set a longer timeout on the socket for listener 
        self._evlConnection.settimeout(_LISTENER_SOCKET_TIMEOUT)

        # initialize the receive buffer
        self._msgBuffer = b""

        return True

    # monitors the EnvisaLink for TPI commands and updates node status in the nodeserver
    # Note: executed on seperate, non-blocking thread
    def _command_listener(self, cmdCallback):

        self._logger.debug("In command_listener()...")

        # loop continuously and listen for TPI commands from EnvisaLink device over socket connection
        while True:

            # get next status message
            cmd_seq = self._get_next_cmd_seq()

            # if the cmd_seq is blank, then an error occurred (either socket error or timeout)
            # NOTE: right now we treat this as an error since the EVL should be broadcasting a time broadcast 
            # every _LISTENER_SOCKET_TIMEOUT seconds. Call function should reconnect
            if cmd_seq is None:
                self._logger.error("No data returned by EnvisaLink device. Probable connection error or timeout. Shutting down socket and listener thread.")
                self._evlConnection.close()
                return

            else:

                # extract the command and data
                cmd = cmd_seq[0]
                data = cmd_seq[1]

                # If the command sequence is an ACK of a sent command (0x0N), handle it here
                if int(cmd, 16) < _CMD_RESPONSE_BASE:
                    
                    # Log any code not equal to success
                    if data != CMD_RESPONSE_CODE_OK:
                        self._logger.warning("Error reponse code returned for last command: %s - %s", data.decode("ascii"), _CMD_RESPONSE_CODES[data])

                    # check to see if listener thread should terminate (leave socket open)
                    if self._stopThread:
                        self._logger.info("Terminating listener thread.")
                        return

                # otherwise, pass the command and data to the callback function for handling
                else:

                    # call status update callback function
                    if cmdCallback is not None:
                        cmdCallback(cmd, data.decode("ascii"))

    # Gets the next full command sequence (delimited by CR/LF pair) from the EnvisaLink
    # Returns: tuple with command and data bytes or None if no data
    def _get_next_cmd_seq(self):

        self._logger.debug("In _get_next_cmd_seq()...")

        # If there is no full command sequence in the buffer, get data from the socket
        while self._msgBuffer.count(b"\r\n") == 0:
            
            try:
                msg = self._evlConnection.recv(_BUFFER_SIZE)
                # uncomment the next line for dumping raw socket data
                #self._logger.debug("Data from socket: %s", msg.decode("ascii"))
            except socket.timeout:
                self._logger.debug("recv() timed out - no data returned.")
                return None
            except socket.error as e:
                self._logger.error("Connection to EnvisaLink unexpectedly closed. Socket error: %s", str(e))
                self._evlConnection.close()
                _msgBuffer = None
                return None
            except:
                raise

            if len(msg) == 0:
                 self._logger.error("Connection to EnvisaLink unexpectedly closed.")
                 return None
            else:
                self._msgBuffer += msg

        # extract command sequence from buffer
        idx = self._msgBuffer.find(b"\r\n")
        seq = self._msgBuffer[:idx]
        self._msgBuffer = self._msgBuffer[idx+2:] # skip CR/LF pair

        # parse the command sequence
        # FORMAT: ^CC,EE$ for ACK, %CC,DATA$ for command from panel
        sentinel = seq[0:1]
        cmd = seq[1:3]
        data = seq[4:seq.find(b"$")]

        # check for acknowledgement of sent command
        if sentinel == b"^": 
            
            # log the received ACK
            self._logger.debug("ACK recived from EnvisaLink: Command %s, Data %s", cmd.decode("ascii"), data.decode("ascii"))

            # return a tuple with the command and data
            return (cmd, data)

        # otherwise check for command from panel
        elif sentinel == b"%":

            # add 0x80 to the command code to differentiate it from ACKs
            if int(cmd, 16) < _CMD_RESPONSE_BASE:
                cmd = format(int(cmd, 16) + _CMD_RESPONSE_BASE, "X").encode("ascii") 
            
            # log the received command 
            self._logger.debug("Command recived from EnvisaLink: Command %s, Data %s", cmd.decode("ascii"), data.decode("ascii"))

            # return a tuple with the command and data
            return (cmd, data)

        # otherwise log warning and return empty
        else:

            self._logger.warning("EnvisaLink returned malformed command sequence: %s", seq.decode("ascii"))
            return None    
    
    # Send command to Envisalink - manage thread lock to prevent stepping on thread
    # Parameters:   cmd - bytearray with 2 digit command
    #               data - data string
    # Returns:      True if command succesful
    def sendCommand(self, cmd, data=""):
           
        self._logger.debug("Sending command to EnvisaLink device: Command %s, Data %s", cmd.decode("ascii"), data)

        # build the command sequence from the command and data 
        # FORMAT: ^CC,DATA$
        cmd_seq = b"^" + cmd + b"," + data.encode("ascii") + b"$" + b"\r\n"
        
        # acquire the send lock
        if self._sendLock.acquire(2):      
    
            # send the command sequence to the EVL
            try:
                self._evlConnection.sendall(cmd_seq)
            except socket.timeout:
                self._logger.error("Unable to communication with EnvisaLink - connection closed.")
                self._evlConnection.close()
                return False
            except socket.error as e:
                self._logger.error("Connection to EnvisaLink unexpectedly closed. Socket error: %s", str(e))
                self._evlConnection.close()
                return False
            except:
                raise
            finally:
                # release the lock
                self._sendLock.release()

            return True

        else:

            self._logger.debug("Cannot acquire lock. Send failed.")

            return False

    # Send keys to Panel - manage thread lock to prevent stepping on thread
    # Parameters:   partition - partition to send keys
    #               keys - keys to send
    # Returns:      True if command succesful
    def sendKeys(self, partition, keys):
           
        self._logger.debug("Sending keys to Alarm Panel - Partition %d, Keys: %s", partition, keys)

        # change the default partition
        if self.sendCommand(CMD_CHANGE_DEFAULT_PARTITION, f"{partition:1d}"):
                  
            # acquire the send lock
            if self._sendLock.acquire(2):      
    
                # send the key sequence
                try:
                    self._evlConnection.sendall(keys.encode("ascii"))
                except socket.timeout:
                    self._logger.error("Unable to communication with EnvisaLink - connection closed.")
                    self._evlConnection.close()
                    return False
                except socket.error as e:
                    self._logger.error("Connection to EnvisaLink unexpectedly closed. Socket error: %s", str(e))
                    self._evlConnection.close()
                    return False
                except:
                    raise
                finally:
                    # release the lock
                    self._sendLock.release()

                return True

            else:

                self._logger.debug("Cannot acquire lock. Send failed.")

                return False
        
        else:
            return False

    # Shutdown listener thread and connection
    def shutdown(self):
           
        self._logger.debug("In shutdown()...")

        # set the stop flag
        self._stopThread = True

        # send a poll command to get EVL to send an ACK (exits recv() wait on socket)
        if self.sendCommand(CMD_POLL):

            # give the listener thread a couple of seconds to end   
            self._listenerThread.join(2.0)

        # close the connection
        self._evlConnection.close()

    # Check the state of the socket connection
    def connected(self):
        if self._evlConnection.fileno() > 0:
            return True
        else:
            return False



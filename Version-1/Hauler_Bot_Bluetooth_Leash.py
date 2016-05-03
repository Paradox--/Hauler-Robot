#----------------------------------------------------------------
# This python class acts as a virtual leash for the Hauler bot. -
#                                                               -
# This Class was based on from the inquiry-with-rssi.py script  -
# that can be found inside the pybluez advanced examples.       -
#                                                               -
# It will attempt to connect to a device and then constantly    -
# recieve the RSSI value. This class and script body is based   -
# off of a script from the bluez example folder.                -
# See: inquiry-with-rssi.py in the advanced examples for the    -
# original script. This one does not attemp to write but        -
# stores the value for other classes to have access to it.      -
# Nicholas Mallonee                                             -
# 3.20.16                                                       -
#----------------------------------------------------------------

'''-----------------------------------------------------------------------------------------------------------
 Notes:                                                                                                      -
 -------------------------------------------------------------------------------------------------------------
 '''
 # This is the leash class, you will need to have the correct MAC address, and Phone Name for it to work
 # if you do not have either, find both from your device and plug them below. Or in the Main Thread.
 # And example is below if you want to use just this class, and what methods you need to call.   
 
#----------------------------------------------------------------
# Libraries and Includes                                        -
#----------------------------------------------------------------
import os
import sys
import struct
import bluetooth
import bluetooth._bluetooth as bluez
import Test_Bluetooth as testBlue
import pygame

#----------------------------------------------------------------
# Bluetooth Leash Class                                         -
#----------------------------------------------------------------
class BluetoothLeash(object):
    def __init__(self, name, address):
        self.currentRSSI = 0
        self.devID = 0;
        self.target_Name = name
        self.target_Address = address
        self.bWasFound = False 

    # -- -- -- --
    # Returns the current RSSI Value 
    def getRSSI(self):
        return self.currentRSSI

    # -- -- -- --
    # Returns If the device was found or not 
    def getFoundDevice(self):
        return self.bWasFound

    # -- -- -- --
    # Sets the new RSSI value
    def setRSSI(self, newRSSI):
        self.currentRSSI = newRSSI

    # -- -- -- --
    # Sets If we found the target device 
    def setFoundDevice(self, newFound):
        self.bWasFound = newFound
    
    # -- -- -- --
    # Prints out the information in a packet struct -- FROM ORIGINAL SCRIPT
    def printpacket(self, pkt):
        for c in pkt:
            sys.stdout.write("%02x " % struct.unpack("B",c)[0])
        print()


    # -- -- -- --
    # Reads the Mode on a socket -- FROM ORIGINAL SCRIPT
    def read_inquiry_mode(self, sock):
        """returns the current mode, or -1 on failure"""
        # save current filter
        old_filter = sock.getsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, 14)

        # Setup socket filter to receive only events related to the
        # read_inquiry_mode command
        flt = bluez.hci_filter_new()
        opcode = bluez.cmd_opcode_pack(bluez.OGF_HOST_CTL, 
            bluez.OCF_READ_INQUIRY_MODE)
        bluez.hci_filter_set_ptype(flt, bluez.HCI_EVENT_PKT)
        bluez.hci_filter_set_event(flt, bluez.EVT_CMD_COMPLETE);
        bluez.hci_filter_set_opcode(flt, opcode)
        sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, flt )

        # first read the current inquiry mode.
        bluez.hci_send_cmd(sock, bluez.OGF_HOST_CTL, bluez.OCF_READ_INQUIRY_MODE )

        pkt = sock.recv(255)

        status,mode = struct.unpack("xxxxxxBB", pkt)
        if status != 0: mode = -1

        # restore old filter
        sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, old_filter )
        return mode

    # -- -- -- -- 
    # Writes the Inquiry Mode -- FROM ORIGINAL SCRIPT
    def write_inquiry_mode(self, sock, mode):
        """returns 0 on success, -1 on failure"""
        # save current filter
        old_filter = sock.getsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, 14)

        # Setup socket filter to receive only events related to the
        # write_inquiry_mode command
        flt = bluez.hci_filter_new()
        opcode = bluez.cmd_opcode_pack(bluez.OGF_HOST_CTL, bluez.OCF_WRITE_INQUIRY_MODE)
        bluez.hci_filter_set_ptype(flt, bluez.HCI_EVENT_PKT)
        bluez.hci_filter_set_event(flt, bluez.EVT_CMD_COMPLETE);
        bluez.hci_filter_set_opcode(flt, opcode)
        sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, flt )

        # send the command!
        bluez.hci_send_cmd(sock, bluez.OGF_HOST_CTL, 
                bluez.OCF_WRITE_INQUIRY_MODE, struct.pack("B", mode) )

        pkt = sock.recv(255)

        status = struct.unpack("xxxxxxB", pkt)[0]

        # restore old filter
        sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, old_filter )
        if status != 0: return -1
        return 0

    # -- -- -- --
    def device_inquiry_with_with_rssi(self, sock):
        # save current filter
        old_filter = sock.getsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, 14)

        # perform a device inquiry on bluetooth device #0
        # The inquiry should last 8 * 1.28 = 10.24 seconds
        # before the inquiry is performed, bluez should flush its cache of
        # previously discovered devices
        flt = bluez.hci_filter_new()
        bluez.hci_filter_all_events(flt)
        bluez.hci_filter_set_ptype(flt, bluez.HCI_EVENT_PKT)
        sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, flt )

        duration = 1
        max_responses = 255
        cmd_pkt = struct.pack("BBBBB", 0x33, 0x8b, 0x9e, duration, max_responses)
        bluez.hci_send_cmd(sock, bluez.OGF_LINK_CTL, bluez.OCF_INQUIRY, cmd_pkt)

        results = []

        done = False
        while not done:
            pkt = sock.recv(255)
            ptype, event, plen = struct.unpack("BBB", pkt[:3])
            if event == bluez.EVT_INQUIRY_RESULT_WITH_RSSI:
                pkt = pkt[3:]
                nrsp = bluetooth.get_byte(pkt[0])
                for i in range(nrsp):
                    addr = bluez.ba2str( pkt[1+6*i:1+6*i+6] )
                    rssi = bluetooth.byte_to_signed_int(
                        bluetooth.get_byte(pkt[1+13*nrsp+i]))
                    results.append( ( addr, rssi ) )
                    #print("[%s] RSSI: [%d]" % (addr, rssi))

                    # If we found the target device print it 
                    if addr == self.target_Address:
                        print("Found The Target: [%s] " % (addr))
                        print("Target's RSSI   : [%s] " % (rssi))

                        # Set the RSSI if we have our target
                        # Set that we found it as well.
                        # Then break out, since we do not need
                        # to search any more.
                        self.setRSSI(rssi)
                        self.setFoundDevice(True)
                        break
            elif event == bluez.EVT_INQUIRY_COMPLETE:
                done = True
            elif event == bluez.EVT_CMD_STATUS:
                status, ncmd, opcode = struct.unpack("BBH", pkt[3:7])
                if status != 0:
                    print("uh oh...")
                    printpacket(pkt[3:7])
                    done = True
            elif event == bluez.EVT_INQUIRY_RESULT:
                pkt = pkt[3:]
                nrsp = bluetooth.get_byte(pkt[0])
                for i in range(nrsp):
                    addr = bluez.ba2str( pkt[1+6*i:1+6*i+6] )
                    results.append( ( addr, -1 ) )
                    print("[%s] (no RRSI)" % addr)
            else:
                print("unrecognized packet type 0x%02x" % ptype)
                self.printpacket(pkt)
                
           # print("event ", event)

        # restore old filter
        sock.setsockopt( bluez.SOL_HCI, bluez.HCI_FILTER, old_filter )

        return results

    # -- -- -- -- -- -- -- -- -- -- -- -- -- --
    def runLeash(self):
        dev_id = 0

        # Set we have not found the device for the next pass
        self.setFoundDevice(False)

        # try to open the dev via the dev id, if not exit
        try:
            sock = bluez.hci_open_dev(dev_id)
        except:
            print("error accessing bluetooth device...")
            sys.exit(1)

        # Try to check the inqury mode
        try:
            mode = self.read_inquiry_mode(sock)
        except Exception as e:
            print("error reading inquiry mode.  ")
            print(e)
            sys.exit(1)
       # print("current inquiry mode is %d" % mode)
        
        
        # inquiry the devices to find the target
        print('Attempting to Find Device')
        self.device_inquiry_with_with_rssi(sock)

    # -- -- -- --
    # Trys to find the device 
    def tryToGetNewRSSI(self):

        # Run the leash
        self.runLeash()

        # Get the new RSSI, if we found it using the leash
        # Otherwise return that we have not found it 
        if(self.getFoundDevice() == True):
            return self.getRSSI()
        else:
            print(' Device was Not Found. ')
            return -999 

    # -- -- -- --
    # Prints the Target if the leash is active
    def isLeashActive(self):
        print(">> Leash is Active: ")
        print('>>       Tar Name is: %s' % (self.target_Name))
        print('>>       Tar Addr is: %s' % (self.target_Address))

         
# -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
# Example of how to use the leash.
# This will seach for a target at name: HTCONE
# And at the Address: 98:0D:2E:22:B6:46
# If it finds the device it will print the rssi, and
# print the address and the RSSI value
# -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
#leash = BluetoothLeash("Phone Name Goes Here", "00:00:00:00:00:00")
#leash.tryToGetNewRSSI()

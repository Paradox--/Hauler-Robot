'''-----------------------------------------------------------------------------------------------------------
 Notes:                                                                                                      -
 -------------------------------------------------------------------------------------------------------------
'''
# This Simply Tests to see if it can find a device. 
# This is used by the Leash
# This is based on a script found in the examples of pybluez

'''-----------------------------------------------------------------------------------------------------------
 Libraries                                                                                                   -
 -------------------------------------------------------------------------------------------------------------
'''
import os
import sys
import struct
import bluetooth
import bluetooth._bluetooth as bluez


'''-----------------------------------------------------------------------------------------------------------
 Script Start:                                                                                               -
 -------------------------------------------------------------------------------------------------------------
'''
print('Searching for Target Device....')

target_name = "HTCONE"
target_address = "98:0D:2E:22:B6:46" 

#nearby_devices = bluetooth.discover_devices(duration=1, lookup_names=True, flush_cache=True, lookup_class=False)

#for bdaddr in nearby_devices:
#    if target_name == bluetooth.lookup_name( bdaddr ):
#        target_address = bdaddr
#        break

#if target_address == "98:0D:2E:22:B6:46":
#    print('Target Device has been found.')
#else:
#    print "Target Device was Not Found."

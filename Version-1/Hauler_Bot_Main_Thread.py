#!/usr/bin/env python
# coding: Latin-1
'''-----------------------------------------------------------------------------------------------------------
 Notes:                                                                                                      -
 -------------------------------------------------------------------------------------------------------------
'''
# Please make sure you have both the pybluez installed on your machine, along with having a PicoBorg Reverse
# that is attached to the Raspberry Pi Bus. 
# If you do not have one you can order one here: https://www.piborg.org/picoborgrev
# 
# Futher note: This is a simple version of the AI. 
# Version: v0.1.0

'''-----------------------------------------------------------------------------------------------------------
 Libraries and Imports                                                                                       -
 -------------------------------------------------------------------------------------------------------------
'''
import PicoBorgRev
import socket
import SocketServer
import threading
import datetime
import random
import time
import math
import sys
from HaulerBot_BlueToothLeash import BluetoothLeash

'''-----------------------------------------------------------------------------------------------------------
 Global Variables                                                                                            -
 -------------------------------------------------------------------------------------------------------------
'''
global PBR                             # For if we time out a connection we need to shut down the motors
global needOverride                    # For if we need to override the AI, set below -- 
global watchDog                        # For setting events in the web service 
needOverride = False

'''-----------------------------------------------------------------------------------------------------------
 Web Service Variables                                                                                       -
 -------------------------------------------------------------------------------------------------------------
'''
webPort = 80                           # Use the Default webport 80 or alt port 8008

'''-----------------------------------------------------------------------------------------------------------
 Set up The Motor Controller                                                                                 -
 -------------------------------------------------------------------------------------------------------------
'''
# Setup the PicoBorg Reverse
PBR = PicoBorgRev.PicoBorgRev()
#PBR.i2cAddress = 0x44                  
PBR.Init()
if not PBR.foundChip:
   boards = PicoBorgRev.ScanForPicoBorgReverse()
   if len(boards) == 0:
       print('No PicoBorg Reverse found, check you are attached :)')
   else:
       print('No PicoBorg Reverse at address %02X, but we did find boards:' % (PBR.i2cAddress)) 
       for board in boards:
           print('    %02X (%d)' % (board, board))
       print('If you need to change the IC address change the setup line so it is correct, e.g.') 
       print('PBR.i2cAddress = 0x%02X' % (boards[0]))
   sys.exit()
#PBR.SetEpoIgnore(True)                 # Uncomment to disable EPO latch, needed if you do not have a switch / jumper
PBR.SetCommsFailsafe(False)             # Disable the communications failsafe
PBR.ResetEpo()

# Movement settings (worked out from our DiddyBorg on a smooth surface)
timeForward1m = 5.7                     # Number of seconds needed to move about 1 meter
timeSpin360   = 4.8                     # Number of seconds needed to make a full left / right spin
testMode = False                        # True to run the motion tests, False to run the normal sequence

# Power settings
voltageIn = 12.0                        # Total battery voltage to the PicoBorg Reverse
voltageOut = 6.0                        # Maximum motor voltage

# Setup the power limits
if voltageOut > voltageIn:
   maxPower = 1.0
else:
   maxPower = voltageOut / float(voltageIn)


'''-----------------------------------------------------------------------------------------------------------
 Motor Controller Class                                                                                      -
 -------------------------------------------------------------------------------------------------------------
'''
class MotorController:
   # Class Constructor 
   def __init__(self):
      self.MotorState = 0                             # 0 State Is motor is stopped, or waiting 
                                                      # 1 State is Motor is moving forward
                                                      # 2 State is turning Left
                                                      # -1 State is moving backwards
                                                      # -2 State is turning Right

   # Returns the current motor state
   # @Return the current motor state code 
   def getMotorState(self):
      return self.MotorState

   # Sets the new Motor state
   # @Param the state to change the motor too 
   # @Return null 
   def setMotorState(self, newState):
      self.MotorState = newState

   # Recieve Information Method
   # @Parm the seconds to sleep for
   # @Param the path to use, or action to use
   # @Return the current action the bot is doing
   def recieveInformation(self, secondsToMove, suggestedPath):
      #Get the state of the bot 
      currentState = self.getMotorState()
      #If we are doing an action that is not what we were doing before 
      if(currentState != suggestedPath):
         #Set the new state as we make a move 
         self.setMotorState(self.makeMove(secondsToMove, suggestedPath))
         #Return the state
         return self.getMotorState()
      else:
         #Make the same move as the last one
         self.makeMove(secondsToMove, self.getMotorState())
         #Return the state
         return self.getMotorState()

   # Make Move Method, tirggers with drive to use 
   # @Param the time to move for
   # @Param the suggested path
   # @Return the action key that we are using
   def makeMove(self, time, path):
      if(time == 0.0):     # If bad time, kill the motor
         self.performMove(0, 0, .25, True)
         return 0
      else:
         if(path == 0):     # Need to Stop
            self.performMove(0, 0, .25, True)
            return 0
         elif (path == 1):  # Need to Go FWD
            self.performMove(1, 1, time, False)
            return 1
         elif (path == -1):  # Need to Go BKD
            self.performMove(-1, -1, time, False)
            return -1
         elif (path == 2):  # Need to Rotate Left 
            self.performTurn(-90.0, time)
            return 2
         elif (path == -2):  # Need to Rotate Right 
            self.performTurn(90.0, time)
            return -2
         else:              # If bad data bring it to a stop
            print('MotorController :: There was an error bringing to stop.')
            self.performMove(0, 0, 10, True)
            print('MotorController :: Attempting to correct data.')
            return 0

   # Preforms the turn
   # @Param Angle to turn
   # @Param the time to turn
   def performTurn(self, angle, time):
      #IF the angle is to the left... 
      if(angle < 0.0):
         leftTrack = -1.0
         rightTrack = +1.0
         angle *= -1
      else: # turn right..
         leftTrack = +1.0
         rightTrack = -1.0
      #Determine total actual time
      time = (angle / 360.0) * timeSpin360
      #Preform the move, then stop after
      self.performMove(leftTrack, rightTrack, time, True)

   # Performs the Action on the motors  
   # @Param the left tread direction
   # @Param the right tread direction
   # @param the time to move for, or sleep for
   # @Param If we need to stop the bot 
   def performMove(self, left, right, timeToMove, needToStop):
      # Run the motors
      PBR.SetMotor1(right * maxPower)
      PBR.SetMotor2(-left * maxPower)
      #Put to sleep 
      time.sleep(timeToMove)
      #If we need to stop, turn of the motors
      if(needToStop == True):
         PBR.MotorsOff()
      
'''-----------------------------------------------------------------------------------------------------------
 AI Brain Class                                                                                              -
 -------------------------------------------------------------------------------------------------------------
'''
# -- -- -- -- 
# NOTE:
# THE BRAIN ONLY SUPPORTS A BLUETOOTH DONGLE THAN SENDS VALUES BETWEEN 0 AND -INF
# PLEASE MAKE SURE THE BLUETOOTH AND WIFI ARE WORKING BEFORE USING!
# USE THE TESTS BELOW TO CHECK THE SYSTEMS! -- Nicholas
# -- -- -- --
class Brain:
   def __init__(self, motorCon, blueLeash):
      # -- Brain Self Varaibles 
      self.lastMoveArray = []                         # Holds the last Move the AI did -- See the Motor controller for codes
      self.lastDistanceArray = []                     # Holds the last known distances for checking 
      self.lastMoveScoreArray = []                    # Holds the effectiveness score
      self.currentKnowDistance = -99                  # Holds the current distance
      self.lastKnowDistance = -99                     # Holds the last known distance to the user
      self.currentThought = 0                         # Holds the current tought to try
      self.lastThought = 0                            # Holds the last tought of the bot
      self.turn = 0                                   # Holds how many steps backwards the bot need to go back in time
      self.MinTolerance = -5                          # Holds the max tolerance to the left of any given distance
      self.MaxTolerance = 5                           # Holds the max tolerance to the right of any given distance
      self.NeedToReverseMoves = False                 # Holds if the bot needs to reverse any moves
      self.HasFinishedReversing = True                # Holds if we just reversed
      self.NeedsToTurn = False                        # Holds if we need to turn
      self.TriedTurnLeft = False                      # Holds if the bot has tried to turn left 
      self.NumOfMovesToReverse = 0                    # Holds the number of moves to reverse 
      # -- Other Classes For Brain to use
      self.motor = motorCon                           # Hook up the motor controller to the brain 
      self.leash =  blueLeash                         # Hook up the leash to the brain 
      
   # Runs the main thread of the brain, which controls all actions
   def runBrain(self):
      # Print that we entered the brain
      print('>>..       Ai Brain is now live        ..<<')
      
      # Varaibles For the run cycle
      bIsRunning = True
      notFoundCounter  = 0
      newRSSI = 0

      # While the bot is running
      while(bIsRunning):
         # Get the RSSI
         newRSSI = self.leash.tryToGetNewRSSI()
         # If we did not find the device, increment the counter
         if(newRSSI == -999):
            notFoundCounter += 1
         else:  # Else if we did find it reset the counter 
            notFoundCounter = 0
         # Print the rssi
         print('>>..       New RSSI Value: %s          ..<<' , newRSSI)

         # If the counter is at 3, stop the bot
         # And wait for it to find it.
         # DO not add it to the array
         if(notFoundCounter >= 1):
            print('>>..       RSSI IS NULL, STOPPING      ..<<')
            self.motor.recieveInformation(0.1, 0)
         else: # Else start the logic for the AI -- -- -- 
           # Check to see if we still need to reverse any moves
           if(self.NeedToReverseMoves == True): #  -- -- 
               # Save the last thought and set the current 
               self.lastThought = self.currentThought
               self.currentThought = self.reverseMove()
               # Decrement the counter and see if its at zero
               self.NumOfMovesToReverse -= 1
               # if the counter is at or less than 0, set to 0 and trip flag
               if(self.NumOfMovesToReverse <= 0):
                  self.NeedToReverseMoves = False
                  self.HasFinishedReversing = True
                  self.NeedsToTurn = True
                  self.NumOfMovesToReverse = 0
               else:
                  # Set that we have not finished reversing 
                  self.HasFinishedReversing = False
               # Finally do the move for 1 second, then stop
               print('>>..       Reversing Move, %d          ..<<', self.currentThought)
               self.motor.recieveInformation(1, self.currentThought)
               self.motor.recieveInformation(.1, 0) 
           # If we do not need to start the other tree -- --  
           else:
            # if we have just finished reversing, try turning 
            if(self.HasFinishedReversing == True):
               self.lastThought = self.currentThought
               # IF we need to turn
               if( self.NeedsToTurn == True):
                  # Notify That we need to turn
                  print('>>..       NEED TO TURN                ..<<')
                  # IF we have not tried to
                  if(self.TriedTurnLeft == False):
                     print('>>..       TURN LEFT                   ..<<')
                     self.currentThought = 2
                     self.NeedsToTurn = False
                     self.TriedTurnLeft = True
                  else:
                     print('>>..       Turn Right                  ..<<')
                     self.currentThought = -2
                     self.NeedsToTurn = False
                     self.TriedTurnLeft = False
                  # Turn the bot
                  self.motor.recieveInformation(1, self.currentThought)
               else:
                  # Save the last thought
                  self.lastThought = self.currentThought
                  # See if we were closer in time 
                  wereCloser =  self.haveBeenCloser( newRSSI, self.lastKnowDistance)
                  # if we were closer, reverse the move, else go forward
                  if(wereCloser == True):
                     print('>>..       Need to Reverse Moves       ..<<')
                     self.NeedToReverseMoves = True
                     self.motor.recieveInformation(1, 0)
                  else:
                     # Notify That we are trying to go forwards.
                     print('>>..       Moving Forwards             ..<<')
                     # save the thought 
                     self.currentThought = 1
                     # add it to the arrays
                     self.addToArrays(self.currentThought, newRSSI, 500)
                     # Do the move
                     self.motor.recieveInformation(1, self.currentThought)
                     self.motor.recieveInformation(.1, 0)
            # Save the last known distance
            self.lastKnowDistance = newRSSI

   # Fills the array of last known moves and distances
   # @Param if this is a test Module
   # If True will display each point
   def generateNullArrays(self):
      i = 0
      #Fill the array with null values:
      #   0 for the moves 
      # -50 for distance
      #   0 for scores
      for i in range(20):
         self.lastMoveArray.append(0)
         self.lastDistanceArray.append(-900)
         self.lastMoveScoreArray.append(0)         
                
   # Add a score to the arrays, and the last move
   # @Parama the move to add
   # @Param the Score to add
   # @Return null 
   def addToArrays(self, move, distance, score):
      #Check the array lenght and adjust if needed 
      if(len(self.lastMoveArray) >= 20):
         self.lastMoveArray.pop(0)
         self.lastDistanceArray.pop(0)
         self.lastMoveScoreArray.pop(0)
      # Add the move and the score to the arrays 
      self.lastMoveArray.append(move)
      self.lastDistanceArray.append(distance)
      self.lastMoveScoreArray.append(score)

   # Returns the last Move of the bot
   # @Return the last move of the bot
   def getLastMove(self):
      return self.lastMoveArray[-1]

   # Returns the last Score
   # @Return the last Move Score
   def getLastScore(self):
      return self.lastMoveScoreArray[-1]

   # Returns the current thought
   # @Return the current path
   def getCurrentThought(self):
      return self.currentThought

   # Returns the last Thought
   # @Returns the last Throught 
   def getLastThought(self):
      return self.lastThought

   # Returns the current Distance
   # @Returns the current distance 
   def getCurrentDistance(self):
      return self.currentKnowDistance

   # Returns the last Distance
   # @Returns the last distance 
   def getLastDistance(self):
      return self.lastKnowDistance

   # Sets the current thought
   # @Param the new thought 
   def setCurrentThought(self, newThought):
      self.currentThought = newThought

   # Sets the last thought
   # @Param the last thought 
   def setLastThought(self, lastThought):
      self.lastThought = lastThought

   # Sets the current Distacne
   # @Param the current dist to sec
   def setCurrentDistance(self, newD):
      self.currentKnowDistance = newD

   # Sets the last dist 
   # @Param the last dist to set
   def setLastDistance(self, lastD):
      self.lastKnowDistance = lastD

   # Searches the Array to see if we have been closer 
   # @Param the current distance
   # @ Return IF we have been closer on this line 
   def haveBeenCloser(self, currentRssi, rssiToTest):
      # Generate the Left and Right bounds
      # These account for RSSI value flux
      boundLeft = currentRssi - 5
      boundRight = currentRssi + 5
      # Test to see where we are in a line

      # If the left bound is greater... 
      if(boundLeft > rssiToTest):
         if(boundRight > rssiToTest):
            return False
         else: # This will not happen, but is fail safe for bad data
            return False
      else:
         if(boundRight >= rssiToTest):
            return False
         else:
            return True

   # Gets the move to do, and removes to move from the arrays
   # Then adds a 0 to the beginning of all arrays or null value
   # @Return the Move to do the opposite of 
   def reverseMove(self):
      # Get the last index 
      moveToDo = self.lastMoveArray[-1]
      # Pop the last indexs from the arrays
      del self.lastMoveArray[-1]
      del self.lastDistanceArray[-1]
      del self.lastMoveScoreArray[-1]      
      # Add to beginning of all arrays a null value
      self.lastMoveArray.insert(0, 0)
      self.lastDistanceArray.insert(0, -900)
      self.lastMoveScoreArray.insert(0, 0)
      # Return the move to do the opposite of
      moveToDo = moveToDo * -1
      return moveToDo      

   # Searches the Array to see if we have been closer 
   # @Param the current distance
   # @Param the last Distance
   # @ Return the value if we are closer or not 
   #def searchArray(self, newRSSI):
      # Search the values to see if we were closer
      
   # Returns how many turns have been in the last 20 moves
   # @ Return the num of turns 
   def getCurrentTurnCount(self,):
      turnCount = 0
      i = 0
      for i in range(20):
         if(self.lastMoveArray[i] == 2):
            turnCount += 1
         elif(self.lastMoveArray[i] == -2):
            turnCount += 1  
      # Return the finished count
      return turnCount

   # Returns the last index of the last turn 
   # @ Returns the las index of turns 
   def getLastTurnIndex(self):
      i = 0
      lastIndex = 0
      for i in range(20):
         if(self.lastMoveArray[i] == 2):
            lastIndex = i
         elif(self.lastMoveArray[i] == -2):
            lastIndex = i
      # Return the last index
      return lastIndex
      
   # Prints the arrays 
   #def printArrays(self):
      #print (self.lastMoveArray, sep =', ')
      #print (self.lastDistanceArray, sep =', ')
      #print (self.lastMoveScoreArray, sep =', ')

   # Prints the array length
   def printArrayLenght(self):
      print(len(self.lastMoveArray))
      print(len(self.lastDistanceArray))
      print(len(self.lastMoveScoreArray))

'''-----------------------------------------------------------------------------------------------------------
 Main Thread                                                                                                 -
 -------------------------------------------------------------------------------------------------------------
'''
# ------ TEST MODULES STARTS HERE ----------------------------------------------------------------------------
# Change if We are testing all or just a module
testMode = False                                                   # Enters the test Mode first 
testMotor = False                                                  # Tests the Motor  
testBluetooth = False                                              # Tests the Bluetooth
testWifi = False                                                   # Tests the WIFI
endWifi = False                                                
testAI = False                                                     # Tests the Ai Brain
test_PrintBrainData = False                                       # Prints the Brains Data During the test 
if(testMode == True):
   print('-------------------------------------------')
   print('-         Starting test Sequence          -')
   print('-_________________________________________-')
   print('- Please make sure the robot is off the   -')
   print('- ground.                                 -')
   print('- These tests make sure all the systems   -')
   print('- are working properly using visual aids  -')
   print('- and output to the console.              -')
   print('-                                         -')
   print('- >> Hauler Bot AI v0.0.9                 -')
   print('- >> Nicholas Mallonee                    -')
   print('-------------------------------------------\n')

   # -- Motor Test Starts Here -- 
   if(testMotor == True): 
      print('>>>>>>>>>>Testing Motor Controller<<<<<<<<<')
      print('>>..  Creating Motor Controller        ..<<')
      motor = MotorController()                                   #Creating class      
      print('>>..  Getting Motor Controller State   ..<<')
      mState = motor.getMotorState()                              #Getting the state 
      print('>>..  Attempting to move forward       ..<<')
      motor.recieveInformation(.25, 1)                            #Attempt forward
      print('>>..  Attempting to move backward      ..<<')
      motor.recieveInformation(.25, -1)                           #Attempt Backwards
      print('>>..  Attempting to Turn Left          ..<<')
      motor.recieveInformation(.25, 0)
      motor.recieveInformation(.25, 2)                            #Attempt left and forward
      motor.recieveInformation(.25, 1)
      print('>>..  Attempting to Turn Right         ..<<')
      motor.recieveInformation(.25, 0)
      motor.recieveInformation(.25, -2)                           #Attempt right and forwards
      motor.recieveInformation(.25, 1)
      print('>>..  Attempting to Stop               ..<<')
      motor.recieveInformation(.25, 0)                            #Attempt to stop 
      print('>>>>>>>>>>Test for Motor COMPLETE<<<<<<<<<<')
      print('\n \n')


   # -- WIFI Test Starts Here --
   if(testWifi == True): 
      print('>>>>>>>>>>Testing Web Server<<<<<<<<<<<<<<<')
      print('>>..  Creating Web Watchdog            ..<<')
      dog = Watchdog()                                                       #Creating Watchdog     
      print('>>..  Creating Web Server              ..<<')
      httpServer = socketserver.TCPServer(("0.0.0.0", webPort), webServer)   #Create the web server
      print('>>..  Please Try Connecting Now        ..<<')
      while(endWifi == False):
         try:
            print(">>..  Press CTRL+C to Stop Test        ..<<")              # Try to handle Requests 
            httpServer.handle_request() 
         except KeyboardInterrupt:                                                                 
            print('>>..  User Input:: Moving on          ..<<')
            endWifi = True
      print('>>..  Rejoining Watchdog Thread        ..<<')                   # Rejoin the Watchdog, and terminate it 
      dog.terminated = True                                   
      dog.join()
      print('>>..  Web Server Termianted Successful ..<<')
      print('>>>>>>>>>>Test for Wifi COMPLETE<<<<<<<<<<<')
      print('\n \n')

   # -- Bluetooth Test Starts Here
   if(testBluetooth == True):
      print('>>>>>>>>>>>Testing BlueTooth<<<<<<<<<<<<<<<')
      print('>>..       Creating Bluetooth Leash    ..<<')
      bLeash = BluetoothLeash("HTCONE", "98:0D:2E:22:B6:46")
      print('>>..       Checking if Leash Is Active ..<<')
      bLeash.isLeashActive()
      print('>>..       Testing Search              ..<<')
      print('>>.. Please make sure you device is on ..<<')
      print('>>.. Each Search Takes 1 Second1       ..<<')
      print('>>..       Search 1                    ..<<')
      bLeash.runLeash()
      print('>>..       Search 2                    ..<<')
      bLeash.runLeash()
      print('>>..       Search 3                    ..<<')
      bLeash.runLeash()
      print('>>..       Ending Search               ..<<')
      print('>>..  If your Device was not found     ..<<')
      print('>>..  Please verify that it is on and  ..<<')
      print('>>..  that it is discovrable.          ..<<')
      print('>>>>>>Test for Bluetooth COMPLETE<<<<<<<<<<')
      print('\n \n')

   # -- AI Brain Test Starts Here --
   if(testAI == True):
      print('>>>>>>>>>>>Testing AI Brain<<<<<<<<<<<<<<<<')
      print('>>..  Creating Brain Class             ..<<')
      bLeash = BluetoothLeash("HTCONE", "98:0D:2E:22:B6:46")      # Create the Leash for the brain
      motorCon  = MotorController()                               # Create the Motor Controller
      brain = Brain(motorCon, bLeash)                             # Creating the AI Brain Class
      print('>>..  Testing Array Filling            ..<<')
      brain.generateNullArrays()                                  # Test to see if the arrays work, set to true to print the null values
      if(test_PrintBrainData == True):
         brain.printArrays()      
      print('>>..  Arrays are now Filled            ..<<')
      print('>>..  Array Lenghts:                   ..<<')
      brain.printArrayLenght()                                    # Prints the array Lenghts
      print('>>..  Testing Array Swaping            ..<<')
      brain.addToArrays(2, -13, 300)                              # Test adding to the arrays
      brain.addToArrays(1, -10, 500)
      brain.addToArrays(-2, -5, 900)
      brain.addToArrays(-1, -9, 200)                              # Test adding to the arrays
      brain.addToArrays(0, -5, 600)
      brain.addToArrays(1, -3, 900)
      print('>>..  Arrays :: Imformation Added      ..<<') 
      if(test_PrintBrainData == True):                            # if the Data needs to be printed
         brain.printArrays()
         print('>>..  Array Lenghts:                   ..<<')
         brain.printArrayLenght()                                 # Prints the lenght 
      print('>>..  Testing Search                   ..<<')
      brain.searchArray(0)
      print('>>>>>>Test for Brain COMPLETE<<<<<<<<<<<<<<')
      print('\n \n')


# -- Else If this is not a test and the real thing -- -- -- -- -- 
else:
   # Print that the bot is starting
   print('>>>>>>>>>>>TStarting Hauler<<<<<<<<<<<<<<<<')
   print('>>..       Hauler Bot is starting      ..<<')
   # Create all the classes.
   print('>>..       Creating classes            ..<<')
   bLeash = BluetoothLeash("HTCONE", "98:0D:2E:22:B6:46")      # Create the Leash for the brain, Change the Name and Mac Address to your own
   motorCon  = MotorController()                               # Create the Motor Controller
   brain = Brain(motorCon, bLeash)                             # Creating the AI Brain Class
   print('>>..       Classes Created             ..<<')
   # Delay the start by 1 minute before the data comes in
   # Allows you to set it down and unplug it all
   # comment out if you want it to start right away
   time.sleep(60)   
   # run the brain..
   print('>>..       Starting Bot Brain Thread   ..<<')
   brain.runBrain()

from pathlib import Path

from core.base.model.AliceSkill import AliceSkill
from core.dialog.model.DialogSession import DialogSession
from core.util.Decorators import IntentHandler


class Broadcast(AliceSkill):
	"""
	Author: Lazza
	Description: Broadcast voice or normal messages to active satellites
		NOTE: Subprocess is used only to copy and delete a sound file when delaying a message
	"""


	# todo Account for multiple delayed messages ?


	def __init__(self):
		self._preChecks: bool = False
		self.satelliteQuantity: int = 0
		self._broadcastMessage: str = ''
		self._playbackDevice: str = ''
		self._selectedSat = None
		self._listOfSatelliteRooms = list()
		self._sendingDevice: str = ''
		self._replying: bool = False
		self._userSpeech = self.AudioServer.LAST_USER_SPEECH
		self._saidYes: bool = False
		self._waveFile = Path(f'{self.getResource("sounds")}/delayedSound.wav')

		super().__init__()


	# NOTE: _selectedSat is same as playbackdevice but is used to allow reference to who i'm having a conversation with

	######################## INTENT HANDLERS ############################

	@IntentHandler('AddBroadcast')
	def addNewBroadcast(self, session: DialogSession, **_kwargs):
		# If UseVoiceRecording is enabled then turn on Alice's voice recording feature
		if self.getConfig('UseVoiceRecording') and not self.getAliceConfig('recordAudioAfterWakeword'):
			self.updateAliceConfig(key='recordAudioAfterWakeword', value=True)
			self.logWarning(f'BroadCast skill has just enabled Alice\'s built in Record Audio After Wakeword feature')

		# This resets values in case of previous broadcast and user initiates another broadcast from a different device
		if self._broadcastMessage:
			self.resetValues()

		# Do prelimanary checks IE: Set the message and or the satellite room
		self.doStatusCheck(session)


	# If user has choosen a room to play on in a multi satellite senario then do this
	@IntentHandler(intent='BroadcastRoom', requiredState='askingWhatRoomToPlayOn', isProtected=True)
	def userChoosingRoom(self, session: DialogSession):

		# is the user choosing the Alice base unit to talk to ?
		if 'GetBase' in session.slots:
			self._playbackDevice: str = self.getAliceConfig('deviceName')
			self._selectedSat = self._playbackDevice
			self.doStatusCheck(session)

		else:
			self.chooseLocation(session)
			self.doStatusCheck(session)


	# Ask user for yes or no responce to playback message now or later (only for users with no available satellites)
	@IntentHandler(intent='AnswerYesOrNo', requiredState='askingIfPlaybackShouldBeNow', isProtected=True)
	def yesOrNoReply(self, session: DialogSession):

		if self.Commons.isYes(session):
			self._saidYes = True
			self.requestMessage(session)

		else:
			self._saidYes = False

			if self._waveFile.exists():
				self.endDialog(
					sessionId=session.sessionId,
					text=self.randomTalk('delayError'),
					siteId=session.siteId
				)

			else:
				self.continueDialog(
					sessionId=session.sessionId,
					text=self.randomTalk('playbackTime'),
					intentFilter=['BroadcastTime'],
					currentDialogState='UserWantsToDelayBroadcast',
					probabilityThreshold=0.1
				)


	# If the user has requested to delay the responce (main unit systems only) then do this
	@IntentHandler(intent='BroadcastTime', requiredState='UserWantsToDelayBroadcast', isProtected=True)
	def delayingBroadcast(self, session: DialogSession):
		# If a duration was specified set a timer
		if 'Duration' in session.slots:
			self._playbackDevice = session.siteId
			self.continueDialog(
				sessionId=session.sessionId,
				text=self.randomTalk('addAMessage'),
				intentFilter=['UserRandomAnswer'],
				currentDialogState='requestingBroadcastMessage',
				probabilityThreshold=0.1
			)


		else:  # if no duration specified ask user again to repeat
			self.continueDialog(
				sessionId=session.sessionId,
				text=self.randomTalk('noConfirmationHeard'),
				intentFilter=['BroadcastTime'],
				currentDialogState='UserWantsToDelayBroadcast',
				probabilityThreshold=0.1
			)


	# Add the broadcast message now that choosing location has been satisfied, and playback to the device
	@IntentHandler(intent='UserRandomAnswer', requiredState='requestingBroadcastMessage', isProtected=True)
	def ProcessFirstInputMessage(self, session: DialogSession):
		self._broadcastMessage: str = session.payload['input']

		if self.satelliteQuantity == 0:
			delayedRecording = Path(self._userSpeech.format(session.user, session.siteId))
			# Copy lastUserSpeech.wav to the sounds folder

			if delayedRecording:
				self.Commons.runSystemCommand(['cp', str(delayedRecording), str(self._waveFile)])

			# if user wants to playback now (no satellite senario)
			if self._saidYes:
				self.playBroadcastMessage(session)
			else:
				delayedInterval: float = self.Commons.getDuration(session)
				self.ThreadManager.doLater(
					interval=delayedInterval,
					func=self.delayedSoundPlaying
				)

				self.endDialog(
					sessionId=session.sessionId,
					text=self.randomTalk('durationConfirmation')
				)

		# if user has at least one active satellite then do this
		elif self.satelliteQuantity >= 1 and self._broadcastMessage and self._playbackDevice:
			self.playBroadcastMessage(session)


	# Below runs when a reply to the initial broadcast is recieved
	@IntentHandler(intent='UserRandomAnswer', requiredState='UserIsReplying', isProtected=True)
	def InputReply(self, session: DialogSession):
		self._playbackDevice = self._sendingDevice
		self._sendingDevice = session.siteId
		self._broadcastMessage = session.payload['input']

		self.playBroadcastMessage(session)


	######### THE CONFIGURATION GROUP ##############

	# This method is used when a user chooses a location
	def chooseLocation(self, session: DialogSession):
		# if user has specified the location in the initial intent do this
		if 'Location' in session.slotsAsObjects:

			# Accounting for different CaseSensitive room names
			spokenLocation: str = session.slotValue('Location')

			listOfCaseOptions = ['spokenLocation.lower()', 'spokenLocation.capitalize()', 'spokenLocation.upper()']
			self._playbackDevice = ''

			for case in listOfCaseOptions:
				tempLocationCase = eval(case)
				if tempLocationCase in self._listOfSatelliteRooms:
					self._playbackDevice: str = tempLocationCase
					self._selectedSat = self._playbackDevice
					return

			if spokenLocation == self.getAliceConfig('deviceName'):
				self._playbackDevice: str = spokenLocation
				self._selectedSat = self._playbackDevice
				return

			if not self._playbackDevice:
				self.continueDialog(
					sessionId=session.sessionId,
					text=self.randomTalk('chooseAnotherLocation'),
					intentFilter=['BroadcastRoom'],
					currentDialogState='askingWhatRoomToPlayOn',
					slot='Location',
					probabilityThreshold=0.1
				)
		else:
			self.continueDialog(
				sessionId=session.sessionId,
				text=self.randomTalk('chooseARoom'),
				intentFilter=['BroadcastRoom'],
				currentDialogState='askingWhatRoomToPlayOn',
				slot='Location',
				probabilityThreshold=0.1
			)


	def setTheActiveDevices(self, session: DialogSession):
		# incomming request was from:
		self._sendingDevice = session.siteId

		# if request is coming from the only available sat then do this
		if self._sendingDevice in self._listOfSatelliteRooms and self.satelliteQuantity == 1:
			self._playbackDevice = self.getAliceConfig('deviceName')
			self._selectedSat = self._playbackDevice
			return
		# else if there are multiple sats and the request is coming from one of them do this
		elif self._sendingDevice in self._listOfSatelliteRooms and self.satelliteQuantity >= 2:
			self.chooseLocation(session)
			return

		# If request is coming from the base unit then do this
		if self.satelliteQuantity == 0:
			# set playback device to the base unit
			self._playbackDevice: str = session.siteId
			self._selectedSat: str = self._playbackDevice

		elif self.satelliteQuantity == 1:
			# set playback to the only satellite the user has
			self._playbackDevice = self._listOfSatelliteRooms[0]
			self._selectedSat: str = self._playbackDevice

		elif self.satelliteQuantity >= 2:
			# Ask user which satellite to use in multi sat senario
			self.chooseLocation(session)


	# Do pre broadcasting checks
	def doStatusCheck(self, session: DialogSession):
		if not self._preChecks:
			self.getAvailableSatRoomNames()  # make a list of available satellite rooms and get quantity
		if not self._selectedSat:
			self.setTheActiveDevices(session)

		if self._selectedSat and 'UserRandomAnswer' not in session.slots and self.satelliteQuantity >= 1:
			self.requestMessage(session)
		elif self._selectedSat and 'UserRandomAnswer' not in session.slots and self.satelliteQuantity == 0:
			self.continueDialog(
				sessionId=session.sessionId,
				text=self.randomTalk('playbackRequest'),
				intentFilter=['AnswerYesOrNo'],
				currentDialogState='askingIfPlaybackShouldBeNow'
			)


	# method for listing all available (active) satellites
	def getAvailableSatRoomNames(self):
		self._listOfSatelliteRooms = list()

		# allow users with alpha branches and/or no heartbeat to play to sats
		if self.getConfig('OnlineSatsOnly'):
			connectedOnly: bool = True

		else:
			connectedOnly: bool = False

		# Get list of satellites
		for device in self.DeviceManager.getDevicesByType('AliceSatellite', connectedOnly=connectedOnly):
			tempListOfRooms = self.LocationManager.getLocation(locId=device.locationID)

			self._listOfSatelliteRooms.append(tempListOfRooms.name)
		# todo larry remove these two test lines (used to pretend i have one sat not two... or zero sats)
		# self._listOfSatelliteRooms = ['Caravan']
		# self._listOfSatelliteRooms = []

		self._preChecks = True

		if self._listOfSatelliteRooms:
			self.logDebug(f'Your list of current locations with satellites are : {self._listOfSatelliteRooms}')
			self.satelliteQuantity = len(self._listOfSatelliteRooms)
		else:
			self.logDebug(f'Seems you have no available satellites at the moment')
			self.satelliteQuantity = 0


	def delayReplyRequest(self):
		self.ask(
			text=self.randomTalk('replyRequest'),
			siteId=self._playbackDevice,
			intentFilter=['UserRandomAnswer'],
			currentDialogState='UserIsReplying',
			canBeEnqueued=False,
			probabilityThreshold=0.2
		)


	# request adding a message
	def requestMessage(self, session: DialogSession):
		self.continueDialog(
			sessionId=session.sessionId,
			text=self.randomTalk('addAMessage'),
			intentFilter=['UserRandomAnswer'],
			currentDialogState='requestingBroadcastMessage',
			probabilityThreshold=0.1
		)


	# Play the broadcast
	def playBroadcastMessage(self, session: DialogSession):
		self.playBroadcastSound()
		# if user has selected to play voice message broadcasts then do this
		if self.getConfig('UseVoiceRecording'):
			lastRecording = Path(self._userSpeech.format(session.user, session.siteId))
			self.playSound(lastRecording.stem, location=lastRecording.parent, siteId=self._playbackDevice)
			self.endSession(sessionId=session.sessionId)

			if self.satelliteQuantity == 0:
				return

			# If user also has choosen to allow replies then do this
			if self.getConfig('AllowReplies') and self.satelliteQuantity >= 1:
				self.ThreadManager.doLater(
					interval=5.0,
					func=self.delayReplyRequest
				)

		elif not self.getConfig('UseVoiceRecording'):

			if self.getConfig('AllowReplies') and self.satelliteQuantity >= 1:

				self.endDialog(
					sessionId=session.sessionId,
					siteId=self._playbackDevice,
					text=self._broadcastMessage
				)

				# add this delay when asking for a reply, for smoother transition
				self.ThreadManager.doLater(
					interval=5.0,
					func=self.delayReplyRequest
				)

			# If no options enabled just end the dialog and play the message
			else:
				self.endDialog(
					sessionId=session.sessionId,
					text=self._broadcastMessage,
					siteId=self._playbackDevice
				)


	def playBroadcastSound(self):
		self.playSound(
			soundFilename='broadcastNotification',
			location=self.getResource('sounds'),
			sessionId='BroadcastAlert',
			siteId=self._playbackDevice
		)


	def resetValues(self):
		self._broadcastMessage: str = ''
		self._playbackDevice: str = ''
		self._selectedSat = None
		self._sendingDevice: str = ''
		self._replying: bool = False
		self._saidYes: bool = False


	# the delayed sound file to play
	def delayedSoundPlaying(self):
		self.playSound(
			soundFilename='delayedSound',
			location=self.getResource('sounds'),
			sessionId='DelayedBroadcastAlert',
			siteId=self._playbackDevice
		)
		self.Commons.runSystemCommand(['rm', str(self._waveFile)])

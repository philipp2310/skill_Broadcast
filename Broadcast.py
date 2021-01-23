from pathlib import Path
from typing import Optional

from core.base.model.AliceSkill import AliceSkill
from core.device.model.DeviceAbility import DeviceAbility
from core.dialog.model.DialogSession import DialogSession
from core.util.Decorators import IntentHandler
from core.device.model.Device import Device


class Broadcast(AliceSkill):
	"""
	Author: Lazza
	Description: Broadcast voice or normal messages to active satellites
	"""


	def __init__(self):
		super().__init__()
		self._preChecksDone: bool = False
		self._deviceQuantity: int = 0
		self._broadcastMessage: str = ''
		self._playbackDevice: Optional[Device] = None
		self._selectedSat: Optional[Device] = None
		self._listOfAllDevices = list()
		self._sendingDevice: Optional[Device] = None
		self._userSpeech = self.AudioServer.LAST_USER_SPEECH
		self._answerReplayNow: bool = False
		self._waveFile = Path(f'{self.getResource("sounds")}/delayedSound.wav')
		self._previousReplyDevice: Optional[Device] = None


	# NOTE: _selectedSat is same as playbackdevice but is used to allow reference to who i'm having a conversation with

	######################## INTENT HANDLERS ############################

	@IntentHandler('AddBroadcast')
	def addNewBroadcast(self, session: DialogSession, **_kwargs):
		# If useVoiceRecording is enabled then turn on Alice's voice recording feature
		if self.getConfig('useVoiceRecording') and not self.getAliceConfig('recordAudioAfterWakeword'):
			self.updateAliceConfig(key='recordAudioAfterWakeword', value=True)
			self.logWarning(f'BroadCast skill has just enabled Alice\'s built in Record Audio After Wakeword feature')

		# This resets values in case of previous broadcast and user initiates another broadcast from a different device
		if self._broadcastMessage:
			self.resetValues()

		# Do prelimanary checks IE: Set the message and or the satellite room
		self.doStatusCheck(session)


	# used for replying to last known device that sent a broadcast
	@IntentHandler('BroadcastReply')
	def reply2LastBroadcast(self, session: DialogSession):
		if not self._previousReplyDevice:
			self.endDialog(
				sessionId=session.sessionId,
				text=self.randomTalk('previousMessageError'),
				siteId=session.siteId
			)
		else:
			if self._previousReplyDevice.uid == session.siteId:
				self.endDialog(
					sessionId=session.sessionId,
					text=self.randomTalk(text='replySelf'),
					siteId=session.siteId
				)
				return

			self._selectedSat = self._playbackDevice = self._previousReplyDevice
			self._sendingDevice = self.DeviceManager.getDevice(uid=session.siteId)
			self.continueDialog(
				sessionId=session.sessionId,
				text=self.randomTalk(text='message4previous', replace=[self._previousReplyDevice]),
				intentFilter=['UserRandomAnswer'],
				currentDialogState='send2previous',
				probabilityThreshold=0.1
			)


	# If user has choosen a room to play on in a multi satellite scenario then do this
	@IntentHandler(intent='BroadcastRoom', requiredState='askingWhatRoomToPlayOn')
	def userChoosingRoom(self, session: DialogSession):
		self.chooseLocation(session)
		self.doStatusCheck(session)


	# Ask user for yes or no responce to playback message now or later (only for users with no available satellites)
	@IntentHandler(intent='AnswerYesOrNo', requiredState='askingIfPlaybackShouldBeNow')
	def yesOrNoReply(self, session: DialogSession):

		if self.Commons.isYes(session):
			self._answerReplayNow = True
			self.requestMessage(session)

		else:
			self._answerReplayNow = False

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
	@IntentHandler(intent='BroadcastTime', requiredState='UserWantsToDelayBroadcast')
	def delayingBroadcast(self, session: DialogSession):
		# If a duration was specified set a timer
		if 'Duration' in session.slots:
			self._playbackDevice = self.DeviceManager.getDevice(uid=session.siteId)
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
	@IntentHandler(intent='UserRandomAnswer', requiredState='requestingBroadcastMessage')
	def ProcessFirstInputMessage(self, session: DialogSession):
		self._broadcastMessage = session.payload['input']
		# SONAR IGNORE
		# self.logInfo(self._broadcastMessage)
		# self.logInfo(self._deviceQuantity)

		if self._deviceQuantity == 1:
			delayedRecording = Path(self._userSpeech.format(session.user, session.siteId))
			# Copy lastUserSpeech.wav to the sounds folder

			if delayedRecording:
				self.Commons.runSystemCommand(['cp', str(delayedRecording), str(self._waveFile)])

			# if user wants to playback now (no satellite senario)
			if self._answerReplayNow:
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
		elif self._deviceQuantity >= 2 and self._broadcastMessage and self._playbackDevice:
			self.playBroadcastMessage(session)


	# Below runs when a reply to the initial broadcast is recieved
	@IntentHandler(intent='UserRandomAnswer', requiredState='UserIsReplying')
	def InputReply(self, session: DialogSession):
		self._playbackDevice = self._sendingDevice
		self._sendingDevice = self.DeviceManager.getDevice(uid=session.siteId)
		self._broadcastMessage = session.payload['input']

		self.playBroadcastMessage(session)


	# Below runs when a reply has been asked by the user
	@IntentHandler(intent='UserRandomAnswer', requiredState='send2previous')
	def ReplyToLastBroadcastDevice(self, session: DialogSession):
		self._broadcastMessage = session.payload['input']

		self.playBroadcastMessage(session)


	######### THE CONFIGURATION GROUP ##############

	# This method is used when a user chooses a location
	def chooseLocation(self, session: DialogSession):
		# if user has specified the location in the initial intent do this
		if 'Location' in session.slotsAsObjects:
			location = self.LocationManager.getLocationByName(session.slotValue('Location'))
			if location:
				self._selectedSat = self.DeviceManager.getDevicesByLocation(locationId=location.id, abilities=[DeviceAbility.PLAY_SOUND])
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
		elif 'GetBase' in session.slots:
			self._selectedSat = self._playbackDevice = self.DeviceManager.getMainDevice()
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
		self._sendingDevice = self.DeviceManager.getDevice(uid=session.siteId)

		# if we are at the only device, we send it to our selves
		if self._deviceQuantity == 1:
			self._selectedSat = self._playbackDevice = self._sendingDevice
		# there are exactly two devices, get the other one
		elif self._deviceQuantity == 2:
			self._selectedSat = self._playbackDevice = [device for device in self._listOfAllDevices if not device == self._sendingDevice][0]
		# there are more devices available - choose by 'Location' slot
		else:
			self.chooseLocation(session)


	# Do pre broadcasting checks
	def doStatusCheck(self, session: DialogSession):
		if not self._preChecksDone:
			self.getAvailableDevices()  # make a list of available devices and get quantity
		if not self._selectedSat:
			self.setTheActiveDevices(session)

		if self._selectedSat and 'UserRandomAnswer' not in session.slots and self._deviceQuantity >= 2:
			self.requestMessage(session)
		elif self._selectedSat and 'UserRandomAnswer' not in session.slots and self._deviceQuantity == 1:
			self.continueDialog(
				sessionId=session.sessionId,
				text=self.randomTalk('playbackRequest'),
				intentFilter=['AnswerYesOrNo'],
				currentDialogState='askingIfPlaybackShouldBeNow'
			)


	# method for listing all available (active) satellites
	def getAvailableDevices(self):

		# "offline sats" allows users with alpha branches and/or no heartbeat to play to sats
		self._listOfAllDevices = self.DeviceManager.getDevicesWithAbilities(abilites=[DeviceAbility.PLAY_SOUND], connectedOnly=self.getConfig('onlineSatsOnly'))
		self._preChecksDone = True

		if self._listOfAllDevices:
			self._deviceQuantity = len(self._listOfAllDevices)
		else:
			self.logDebug(f'Seems you have no available devices at the moment')
			self._deviceQuantity = 0


	def delayReplyRequest(self):
		self.ask(
			text=self.randomTalk('replyRequest'),
			siteId=self._playbackDevice.uid,
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
		# self.logInfo(self._sendingDevice)
		self._previousReplyDevice = self._sendingDevice
		self.playBroadcastSound()
		# if user has selected to play voice message broadcasts then do this
		if self.getConfig('useVoiceRecording'):
			lastRecording = Path(self._userSpeech.format(session.user, session.siteId))
			self.playSound(lastRecording.stem, location=lastRecording.parent, siteId=self._playbackDevice.uid)
			self.endSession(sessionId=session.sessionId)

			if self._deviceQuantity == 1:
				return

			# If user also has choosen to allow replies then do this
			if self.getConfig('allowReplies') and self._deviceQuantity >= 2:
				self.ThreadManager.doLater(
					interval=5.0,
					func=self.delayReplyRequest
				)

		elif not self.getConfig('useVoiceRecording'):

			if self.getConfig('allowReplies') and self._deviceQuantity >= 2:
				self.endDialog(
					sessionId=session.sessionId,
					siteId=self._playbackDevice.uid,
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
					siteId=self._playbackDevice.uid
				)


	def playBroadcastSound(self):
		self.playSound(
			soundFilename='broadcastNotification',
			location=self.getResource('sounds'),
			sessionId='BroadcastAlert',
			siteId=self._playbackDevice.uid
		)


	def resetValues(self):
		self._broadcastMessage: str = ''
		self._selectedSat = None
		self._playbackDevice = None
		self._sendingDevice = None
		self._answerReplayNow: bool = False


	# the delayed sound file to play
	def delayedSoundPlaying(self):
		self.playSound(
			soundFilename='delayedSound',
			location=self.getResource('sounds'),
			sessionId='DelayedBroadcastAlert',
			siteId=self._playbackDevice.uid
		)
		self.Commons.runSystemCommand(['rm', str(self._waveFile)])

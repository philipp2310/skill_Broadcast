# Broadcast

[![Continous Integration](https://gitlab.com/project-alice-assistant/skills/skill_Broadcast/badges/master/pipeline.svg)](https://gitlab.com/project-alice-assistant/skills/skill_Broadcast/pipelines/latest) [![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=project-alice-assistant_skill_Broadcast&metric=alert_status)](https://sonarcloud.io/dashboard?id=project-alice-assistant_skill_Broadcast)

Broadcast voice message to satellites

- Author: Lazza
- Maintainers: 
- Alice minimum Version: 1.0.0-b1
- Languages:
    en
    
**Broadcast Skill - General description**

The Broadcast skill is designed to allow you to send a message to another device such as a satellite.

 EG: You say => "Send a Broadcast" or "Broadcast to the bedroom"
    Alice says => "Please add a message to broadcast"
    You say => "Dinner is ready in five minutes"
    Alice Then broadcasts the message to a selected Satellite 
    
- If you don't have a second device on the network (or your satellite is offline)  Alice will replay the message back
    to you on the device requested from. This might be of use if you want to test your system or send a delayed 
    message to your wife as a little suprise... EG: "You look good today".
    
**Settings**

In the 'skill' tab on the web interface, click "skill settings" on the broadcast skill. There are three options in there

1. UseVoiceRecording - This feature when enabled (default setting) will play your voice recording as the playback message.
                        NOTE : This feature will only work for one message currently if you delay a message in a no satellite senario
2. AllowReplies - Enabling this (default setting) allows Alice to expect replies to a initial broadcast so you can have back and forth 
                    conversatios with someone via broadcasting, disabling will send the initial broadcast and then
                     end the session.
3. OnlineSatsOnly - Enable this (not enabled by default) if you have the latest satellite branch and satellite widget installed
                    which uses heartbeats to detect if satellite is currently online or not
                    - disable this if you are on alpha a1 or earlier version of the satellite branch which
                     does not use the heartbeat code
- Usage examples
    
    *(common usage)*
    - "Hey Snips/Alice"
    - "Send a broadcast."
    - "Bring me a beer when you come outside next please"

    *(usage example with replies enabled)*
    - "Hey Snips/Alice"
    - "Broadcast to the kids room"
    - "It's time to start your homework"
    - kids then reply back to main unit ..."but i don't want too"
    - You then reply ... "insert bribery responce here " :)
    
    *(usage example with no satellites)*
    - "Hey Snips/Alice"
    - "Send a broadcast"
    - Alice.... "What message do you want to send"
    - you ..... "Just want to remind you that i love you"
    - Alice ... "Do you want to play that back now ?"
    - You ..... "No"
    - Alice.... "When do you want to play that back then ?"
    - You  .... "In 3 hours"
        
- **Special NOTE**

- Enabling UseVoiceRecordning option in settings will also automatically enable 
    the voice recording on wakeword feature built into Alice (found in the admin Web UI)

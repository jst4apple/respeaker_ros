#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Yuki Furuta <furushchev@jsk.imi.i.u-tokyo.ac.jp>
import sys
import os
reload(sys)
sys.setdefaultencoding('utf8')

import actionlib
import rospy
import speech_recognition as SR
from aip import AipSpeech

APP_ID = os.environ['BAIDU_APP_ID']
API_KEY = os.environ['BAIDU_API_KEY'] 
SECRET_KEY = os.environ['BAIDU_SECRET_KEY'] 


from actionlib_msgs.msg import GoalStatus, GoalStatusArray
from audio_common_msgs.msg import AudioData
from sound_play.msg import SoundRequest, SoundRequestAction, SoundRequestGoal
from speech_recognition_msgs.msg import SpeechRecognitionCandidates


class SpeechToText(object):
    def __init__(self):
        # format of input audio data
        self.sample_rate = rospy.get_param("~sample_rate", 16000)
        self.sample_width = rospy.get_param("~sample_width", 2L)
        # language of STT service
        self.language = rospy.get_param("~language", "ja-JP")
        # ignore voice input while the robot is speaking
        self.self_cancellation = rospy.get_param("~self_cancellation", True)
        # time to assume as SPEAKING after tts service is finished
        self.tts_tolerance = rospy.Duration.from_sec(
            rospy.get_param("~tts_tolerance", 1.0))

        self.recognizer = AipSpeech(APP_ID, API_KEY, SECRET_KEY)

        self.tts_action = None
        self.last_tts = None
        self.is_canceling = False
	self.is_sound_init = False

        self.pub_speech = rospy.Publisher(
            "speech_to_text", SpeechRecognitionCandidates, queue_size=1)
        #self.sub_audio = rospy.Subscriber("audio", AudioData, self.audio_cb)
        self.sub_audio = rospy.Subscriber("speech_audio", AudioData, self.audio_cb)

    def init_sound(self):
        if self.self_cancellation:
            self.tts_action = actionlib.SimpleActionClient(
                "sound_play", SoundRequestAction)
            if self.tts_action.wait_for_server(rospy.Duration(5.0)):
                self.tts_timer = rospy.Timer(rospy.Duration(0.1), self.tts_timer_cb)
            else:
                rospy.logerr("action '%s' is not initialized." % rospy.remap_name("sound_play"))
                self.tts_action = None

    def tts_timer_cb(self, event):
        stamp = event.current_real
        active = False
        for st in self.tts_action.action_client.last_status_msg.status_list:
            if st.status == GoalStatus.ACTIVE:
                active = True
                break
        if active:
            if not self.is_canceling:
                rospy.logdebug("START CANCELLATION")
                self.is_canceling = True
                self.last_tts = None
        elif self.is_canceling:
            if self.last_tts is None:
                self.last_tts = stamp
            if stamp - self.last_tts > self.tts_tolerance:
                rospy.logdebug("END CANCELLATION")
                self.is_canceling = False

    def audio_cb(self, msg):
        #if not self.is_sound_init: 
        #    self.init_sound()

        if self.is_canceling:
            rospy.loginfo("Speech is cancelled")
            return
        data = SR.AudioData(msg.data, self.sample_rate, self.sample_width)
        try:
            rospy.loginfo("Waiting for result %d" % len(data.get_raw_data()))
            result = self.recognizer.asr(data.get_raw_data(), 'pcm', 16000, {
                    'dev_pid': 1936#1536,
                    })
            if result['err_no']:
                #rospy.loginfo(result["err_msg"])
                return
            rospy.loginfo(";".join(result["result"]))
            #result = self.recognizer.recognize_google(
            #    data, language=self.language)
            #msg = SpeechRecognitionCandidates(transcript=[result])
            #self.pub_speech.publish(msg)
        except SR.UnknownValueError as e:
            rospy.logerr("Failed to recognize: %s" % str(e))
        except SR.RequestError as e:
            rospy.logerr("Failed to recognize: %s" % str(e))


if __name__ == '__main__':
    rospy.init_node("speech_to_text")
    stt = SpeechToText()
    rospy.spin()

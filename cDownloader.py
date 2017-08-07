import argparse
import codecs
import datetime
import json
import logging
import os.path
import threading

from socket import error as SocketError
from socket import timeout
from ssl import SSLError
from urllib2 import URLError

import cLogger, cComments
import sys, os, time

from httplib import HTTPException
from instagram_private_api_extensions import live

class NoBroadcastException(Exception):
	pass

def main(apiArg, recordArg):
	global api
	global record
	global isRecording
	isRecording = False
	api = apiArg
	record = recordArg
	getUserInfo(record)

def recordStream(broadcast):
	try:
		dl = live.Downloader(
			mpd=broadcast['dash_playback_url'],
			output_dir='{}_output_{}/'.format(record, broadcast['id']),
			user_agent=api.user_agent)
	except Exception as e:
		cLogger.log('[E] Could not start recording broadcast: ' + str(e), "RED")
		cLogger.seperator("GREEN")
		sys.exit(0)

	try:
		cLogger.log('[I] Starting broadcast recording.', "GREEN")
		dl.run()
	except KeyboardInterrupt:
		cLogger.log('', "GREEN")
		cLogger.log('[I] Aborting broadcast recording.', "GREEN")
		if not dl.is_aborted:
			dl.stop()
	finally:
		isRecording = False
		t = time.time()
		cLogger.log('[I] Stitching downloaded files into video.', "GREEN")
		dl.stitch(record + "_" + str(broadcast['id']) + "_" + str(int(t)) + '.mp4')
		cLogger.log('[I] Successfully stitched downloaded files.', "GREEN")
		cLogger.seperator("GREEN")
		sys.exit(0)


def getUserInfo(record):
	try:
		user_res = api.username_info(record)
		user_id = user_res['user']['pk']
		getBroadcast(user_id)
	except Exception as e:
		cLogger.log('[E] Could not get user info: ' + str(e), "RED")
		cLogger.seperator("GREEN")
		sys.exit(0)


def getBroadcast(user_id):
	try:
		cLogger.log('[I] Checking broadcast for "' + record + '".', "GREEN")
		broadcast = api.user_broadcast(user_id)
		if (broadcast is None):
			raise NoBroadcastException('No broadcast available.')
		else:
			recordStream(broadcast)
	except NoBroadcastException as e:
		cLogger.log('[W] ' + str(e), "YELLOW")
		cLogger.seperator("GREEN")
		sys.exit(0)
	except Exception as e:
		if (e.__name__ is not NoBroadcastException):
			cLogger.log('[E] Could not get broadcast info: ' + str(e), "RED")
			cLogger.seperator("GREEN")
			sys.exit(0)
#!/usr/bin/python
# -*- coding: utf-8 -*-

import httplib2
import os
import sys
import re
import string
import dateutil.parser
import threading
import random
import urllib2
import requests
import urllib
import json
import sys
import base64
import hashlib
import MySQLdb

from thread import *
from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

import time
from datetime import datetime
from pytz import timezone
from datetime import datetime, timedelta
from requests.auth import HTTPDigestAuth
encoding = "utf-8" 

CLIENT_SECRETS_FILE = "chatBot_secrets.json"

YOUTUBE_READ_WRITE_SCOPE = "https://www.googleapis.com/auth/youtube"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

MISSING_CLIENT_SECRETS_MESSAGE = """
WARNING: Please configure OAuth 2.0

To make this sample run you will need to populate the client_secrets.json file
found at:

   %s

with information from the Developers Console
https://console.developers.google.com/

For more information about the client_secrets.json file format, please visit:
https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
""" % os.path.abspath(os.path.join(os.path.dirname(__file__),
                                   CLIENT_SECRETS_FILE))

VALID_BROADCAST_STATUSES = ("all", "active", "completed", "upcoming",)

LAST_MSG = 0
FIRST = 0
READING = 0
ID_LIST = []
MSG_LIST = []
BOT_NAMES = []

def get_authenticated_service(args):
  flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE,
    scope=YOUTUBE_READ_WRITE_SCOPE,
    message=MISSING_CLIENT_SECRETS_MESSAGE)

  storage = Storage("%s-oauth2.json" % sys.argv[0])
  credentials = storage.get()

  if credentials is None or credentials.invalid:
    credentials = run_flow(flow, storage, args)

  return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
    http=credentials.authorize(httplib2.Http()))

# fetches new messages in the chat
def get_messages(youtube, pagetoken = ""):
  global LAST_MSG
  global FIRST
  global CHAT_ID
  global READING
  global ID_LIST
  global MSG_LIST
  global BOT_NAMES

  maxRes = 0
  if FIRST == 0:
    maxRes = 200
  else:
    maxRes = 2000
  
  if pagetoken != "":
    message_request = youtube.liveChatMessages().list(
      liveChatId=CHAT_ID,
      part="id,snippet,authorDetails",
      pageToken=pagetoken,
      maxResults=maxRes
    )
  else:
    message_request = youtube.liveChatMessages().list(
      liveChatId=CHAT_ID,
      part="id,snippet,authorDetails",
      maxResults=maxRes
    )

  try:
    message_response = message_request.execute()
  except Exception as e:
    print e

    time.sleep(10)
    get_messages(youtube, pagetoken)
    return

  time.localtime()

  totalResults = message_response["pageInfo"]["totalResults"]
  resultsPerPage = message_response["pageInfo"]["resultsPerPage"]
  if totalResults == 0:
      READING = 1
      return

  if FIRST == 0:
    message_response.get("items", [])[0]

    date = dateutil.parser.parse(message_response.get("items", [])[0]["snippet"]["publishedAt"].encode('utf_8'))
    timeString = str(date)
    timeString = timeString.split('.')[0]
    timeString = timeString.split('+')[0]
    unix = time.mktime(datetime.strptime(timeString, "%Y-%m-%d %H:%M:%S").timetuple())

    print "Start: %d" % (LAST_MSG)

  for message in message_response.get("items", []):
    chatID = message["id"]

    if chatID in ID_LIST:
      continue
    ID_LIST.append(chatID)

    publishedTime = message["snippet"]["publishedAt"]

    # time to Unix Timestamp
    date = dateutil.parser.parse(publishedTime)
    timeString = str(date)
    timeString = timeString.split('.')[0]
    timeString = timeString.split('+')[0]
    unix = time.mktime(datetime.strptime(timeString, "%Y-%m-%d %H:%M:%S").timetuple())

    if LAST_MSG >= unix and FIRST == 0:
      continue
    LAST_MSG = unix

    msg = message["snippet"]["displayMessage"]
    isChatOwner = message["authorDetails"]["isChatOwner"]
    isChatModerator = message["authorDetails"]["isChatModerator"]
    msgType = message["snippet"]["type"]

    if msgType == 'tombstone':
      continue

    if isChatModerator == True or isChatOwner == True:
      if msg == "!stop":
        MSG_LIST = []
        print "STOPPING"
        return

    MSG_LIST.append(message)
    #print msg

  # update first message to done
  FIRST = 1

  # sleep specific amount of seconds
  sleep = message_response["pollingIntervalMillis"] / 1000
  time.sleep(sleep)

  # read other page if exists
  if message_response["nextPageToken"] == "":
    get_messages(youtube, "")
    return
  else:
    get_messages(youtube, message_response["nextPageToken"])
    return

def is_word_in_text(word, text):
    pattern = r'(^|[^\w]){}([^\w]|$)'.format(word)
    pattern = re.compile(pattern, re.IGNORECASE)
    matches = re.search(pattern, text)
    return bool(matches)

def checkBlacklist(youtube, name, user):
  global CHAT_ID
  global BOT_NAMES

  for bot in BOT_NAMES:
    if bot['name'] in name:

      try:
        request = youtube.liveChatBans().insert(
            part="snippet",
            body={
              "snippet": {
                "liveChatId": CHAT_ID,
                "type": "permanent",
                "bannedUserDetails": {
                  "channelId": user
                }
              }
            }
        )
        response = request.execute()
      except:
        print "Ban failed"
      return

def checkNames(youtube):
  global MSG_LIST

  while (True):
    timestamp = time.time()
    next_timestamp = timestamp + 1
    time.sleep(next_timestamp - timestamp)
    timestamp = next_timestamp

    msgs = MSG_LIST

    if len(msgs) > 0:
      print "--- check %d names ---" % (len(msgs))

      for msg in msgs:
        name = msg["authorDetails"]["displayName"]
        user = msg["snippet"]["authorChannelId"]

        print "checking %s" % (name)
        checkBlacklist(youtube, name, user)
        MSG_LIST.remove(msg)

def getList():
  global BOT_NAMES

  while (True):
    timestamp = time.time()
    next_timestamp = timestamp + 1
    time.sleep(next_timestamp - timestamp)
    timestamp = next_timestamp

    if timestamp % 1000:
      print "--- update list ---"
      r = requests.get('https://blacklist.501-legion.de/get_list.php')

      BOT_NAMES = r.json()

# Remove keyword arguments that are not set
def remove_empty_kwargs(**kwargs):
  good_kwargs = {}
  if kwargs is not None:
    for key, value in kwargs.iteritems():
      if value:
        good_kwargs[key] = value
  return good_kwargs

def search_list_live_events(youtube, **kwargs):
  kwargs = remove_empty_kwargs(**kwargs)

  response = youtube.search().list(
    **kwargs
  ).execute()
  return response

def search_by_id(youtube, **kwargs):
  kwargs = remove_empty_kwargs(**kwargs)

  response = youtube.search().list(
    **kwargs
  ).execute()
  return response

def videos_list_by_id(youtube, **kwargs):
  kwargs = remove_empty_kwargs(**kwargs)

  response = youtube.videos().list(
    **kwargs
  ).execute()
  return response

def setLiveChatID(youtube):
  global CHAT_ID
  global VIDEO_ID
  global CHANNEL_ID

  response = search_by_id(youtube,
    part="snippet",
        channelId=CHANNEL_ID,
        eventType="live",
        maxResults=1,
        type="video")

  result = response.get("items", [])

  if len(result) == 0:
    print "Stream offline ... waiting 5 minutes"
    timestamp = time.time()
    next_timestamp = timestamp + 10
    time.sleep(next_timestamp - timestamp)
    setLiveChatID(youtube)
    return

  VIDEO_ID = result[0]["id"]["videoId"]
  print "Stream retrieved"

  response = videos_list_by_id(youtube,
    part='liveStreamingDetails,snippet',
    id=VIDEO_ID)
  CHAT_ID = response.get("items", [])[0]["liveStreamingDetails"]["activeLiveChatId"]
  print "Chat retrieved"

def main():
  global READING
  global CHANNEL_ID
  
  reload(sys)
  sys.setdefaultencoding('utf8')

  if len(sys.argv) == 2:
    if sys.argv[1] == "--noauth_local_webserver":
      args = argparser.parse_args()
    else:
      CHANNEL_ID = sys.argv[1]
      args = ""
  else:
    args = argparser.parse_args()

  print args
  youtube = get_authenticated_service(args)

  setLiveChatID(youtube)
  youtube = get_authenticated_service(args)
  start_new_thread(checkNames, (youtube, ))
  start_new_thread(getList, ())
  get_messages(youtube)

  while (True):
    timestamp = time.time()
    next_timestamp = timestamp + 1
    time.sleep(next_timestamp - timestamp)
    timestamp = next_timestamp

    if READING == 1:
      READING = 0
      get_messages(youtube)

if __name__ == "__main__":
  main()

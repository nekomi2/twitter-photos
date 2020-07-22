# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, absolute_import
import tweepy
import atexit
import collections
import json
import os
import sys
import datetime
# Import .settings before twitter due to local development of python-twitter
from .settings import (CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN,
					   ACCESS_TOKEN_SECRET, COUNT_PER_GET, MEDIA_SIZES,
					   PROGRESS_FORMATTER, TIMELINE_TYPES, TEST_DATA)
from .utils import download, create_directory
from .cli import parse_args

class TwitterPhotos(object):

	def __init__(self, user=None,num=None, exclude_replies=False, tl_type=None,filter=False):
		"""
		:param user: The screen_name of the user whom to return results for
		:param list_slug: The slug identifying the list owned by the `user`
		:param outdir: The output directory (absolute path)
		:param num: Number of most recent photos to download from each
			related user
		:param parallel: A boolean indicating whether parallel download is
			enabled
		:param increment: A boolean indicating whether to download only new
			photos since last download
		:param: Photo size represented as a string (one of `MEDIA_SIZES`)
		:param: A boolean indicating whether to exlude replies tweets
		:param type: Timeline type represented as a string (one of `TIMELINE_TYPES`)
		:param test: A boolean indicating whether in test mode
		"""
		self.user = user
		self.list_slug = list_slug
		self.num = num
		self.exclude_replies = exclude_replies
		self.tl_type = tl_type
		self.filter = filter
        auth = tweepy.AppAuthHandler(consumer_key=CONSUMER_KEY,
                                consumer_secret=CONSUMER_SECRET)
        self.api = tweepy.API(auth)
		self.photos = []
        self.idx = 0
		self._downloaded = 0
		self._total = 0

    def load(self, user=None, limit=None):
            if self.tl_type == 'favorites':
                statuses = tweepy.Cursor(self.api.favorites,
                                        id=user,
                                        ).items(limit=limit)
            elif(self.list_slug):
                statuses = tweepy.Cursor(self.api.list_timeline,
                                        slug=self.list_slug,
                                        ).items(limit=limit)
            else:
                statuses = tweepy.Cursor(self.api.user_timeline,id=user,
                                        ).items(limit=limit)

            fetched_photos = []
            for s in statuses:
                print(++idx)
                if 'media' in s.entities:
                    for m in s.entities['media']:
                        if m['type'] == 'photo':
                            t = (m['id'], m['media_url'])
                            fetched_photos.append(t)
            self.photos = fetched_photos

    def download(self, size=None):
        if size is None:
            size = self.size or 'large'
        if size not in MEDIA_SIZES:
            raise Exception('Invalid media size %s' % size)
            d = os.path.join(self.outdir or '', self.user)
            # Create intermediate directory
            create_directory(d)
            self._download_photos(self.photos, self.user, d, size)

def new_line():
	sys.stdout.write('\n')


def main():
	args = parse_args()
	twphotos = TwitterPhotos(user=args.user,
							 list_slug=args.list_slug,
							 outdir=args.outdir,
							 num=args.num,
							 size=args.size,
							 exclude_replies=args.exclude_replies,
							 tl_type=args.type,
							 filter = args.filter
							 )
    twphotos.load()
    twphotos.download()


# Register cleanup functions
atexit.register(new_line)
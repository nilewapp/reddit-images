#!/usr/bin/env python
import argparse
import logging
import math
import os
import praw
import shutil
import signal
import sys
import tempfile
import time
import urllib
import urllib.parse as urlparse
import urllib.request as urlreq
import yaml
from PIL import Image

version = '0.1'
name = 'reddit-images'
fullname = '{} version {}'.format(name, version)

rm_old = False
prev_images = set()
logger = None

def cleanup(signum, frame):
    global rm_old
    global prev_images
    logger.info('Cleanup %s %s', rm_old, prev_images)
    if rm_old:
        for u in prev_images:
            remove(u[1])
    sys.exit()

def remove(path):
    logger.info('Remove %s', path)
    os.remove(path)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def image_path(dir, urlstr):
    url = urlparse.urlparse(urlstr)
    return '{}/{}{}'.format(dir, url.netloc.replace('.', '_'), url.path.replace('/', '_'))

def rewrite_url(urlstr):
    url = urlparse.urlparse(urlstr)
    if url.netloc.endswith('imgur.com') and not url.path.startswith('/a/'):
        u = 'https://i.imgur.com{}'.format(url.path.replace('/gallery', '', 1))
        if not u.endswith('.jpg'):
            u += '.jpg'
        return u
    else:
        return '{url.scheme}://{url.netloc}{url.path}'.format(url=url)

def user_agent(url, user):
    prj = '{} from {}'.format(fullname, url)
    if user == None:
        return prj
    else:
        return '{} with {}'.format(user, prj)

def download(url, ofile):
    with urlreq.urlopen(url) as response:
        logger.info('Download %s', url)
        shutil.copyfileobj(response, ofile)
        ofile.seek(0)

def main():
    global rm_old
    global prev_images
    global logger

    parser = argparse.ArgumentParser(prog='reddit-images')
    parser.add_argument('config_file')
    args = parser.parse_args()

    iteration = 0

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(name)

    logger.info('Starting %s', name)

    while True:
        with open(args.config_file) as cfgfile:
            cfg = yaml.load(cfgfile)

            period = cfg['period']
            dir = cfg['download-directory']
            rm_old = cfg['remove-previous-image']
            user = cfg['reddit-user']
            url = cfg['project-url']
            max_images = cfg['max-images']
            max_downloads = max_images
            subreddits = '+'.join(set(cfg['subreddits']))
            min_width = cfg['min-width']
            min_height = cfg['min-height']

            if not os.path.isdir(dir):
                os.makedirs(dir)

            results = praw.Reddit(user_agent=user_agent(url, user)).get_subreddit(subreddits)

            iteration = iteration + 1
            logger.info('Iteration %s', iteration)

            urls = []

            try:
                urls = results.get_hot(limit=max_downloads)
            except:
                logger.info('Failed to get hot links')
                time.sleep(5)
                continue

            urls = [ rewrite_url(s.url) for s in urls ]
            urls = [ u for u in urls if u.endswith('.jpg') ]

            urls = set(urls[:max_images])
            images = set([ (u,image_path(dir, u)) for u in urls ])

            for new_image in images - prev_images:
                try:
                    with tempfile.TemporaryFile() as tmpfile:
                        download(new_image[0], tmpfile)

                        im = Image.open(tmpfile)

                        if im.width < cfg['min-width'] and im.height < cfg['min-height']:
                            logger.info('Rejecting small image %s (dimensions %dx%d)', new_image[0], im.width, im.height)
                            continue

                        tmpfile.seek(0)
                        with open(new_image[1], 'wb') as ofile:
                            shutil.copyfileobj(tmpfile, ofile)

                except urllib.error.HTTPError:
                    logger.info('Failed to download %s', new_image[0])
                    continue

                prev_images.add(new_image)

            for old_image in prev_images - images:
                remove(old_image[1])
                prev_images.discard(old_image)

            # Simple way of finding the number of urls needed to
            # get the desired number of images
            if num_urls != max_images:
                max_downloads = math.ceil(max_downloads*max_images/len(prev_images))

            time.sleep(period)

    logger.info('Exiting %s', name)

if __name__ == "__main__":
    main()

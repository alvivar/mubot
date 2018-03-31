import datetime
import json
import os
import re
import sys
import time
from random import shuffle

import requests
from bs4 import BeautifulSoup

import selenium.webdriver.support.ui as ui
from selenium import webdriver
from selenium.webdriver.common.keys import Keys

COW = r"""
         (__)
         (oo)
  /-------\/
 / |     ||
+  ||----||
   ~~    ~~  mubot v0.1 """

DELTA = time.time()
TIMESTR = round(DELTA)

HOME = os.path.normpath(  # The script directory + cxfreeze compatibility
    os.path.dirname(
        sys.executable if getattr(sys, 'frozen', False) else __file__))

TODAY = datetime.datetime.today()
TODAYSTR = f'{TODAY.year}{TODAY.month:02}{TODAY.day:02}'
DATAPATH = os.path.join(HOME, 'data', TODAYSTR)
if not os.path.exists(DATAPATH):
    os.makedirs(DATAPATH)

CHROMEDRIVER = os.path.join(HOME, 'chromedriver.exe')


def get_html(url):

    driver = webdriver.Chrome(CHROMEDRIVER)
    driver.maximize_window()
    driver.get(url)
    html = driver.page_source
    driver.quit()

    return html


def get_threads_from_catalog(html):

    soup = BeautifulSoup(html, 'html.parser')
    threads = soup.find('div', {
        'id': 'threads'
    }).find_all('div', {'class': 'thread'})

    data = []
    for i in threads:

        url = i.find('a', {'href': True})
        url = url['href'] if url else False

        teaser = i.find('div', {'class': 'teaser'})
        teaser = teaser.text.strip() if teaser else False

        special = i.find('div', {'class': 'threadIcons'})
        special = True if special else False

        soundcloud = 'soundcloud' in teaser.lower()
        bandcamp = 'bandcamp' in teaser.lower()

        stats = i.find('div', {'class': 'meta'}).find_all('b')
        try:
            replies_count = stats[0].text
        except IndexError:
            replies_count = 0
        try:
            images_count = stats[1].text
        except IndexError:
            images_count = 0

        data.append({
            'url': f'https:{url}',
            'teaser': teaser,
            'special': special,
            'soundcloud': soundcloud,
            'bandcamp': bandcamp,
            'replies_count': int(replies_count),
            'images_count': int(images_count)
        })

    return data


def get_replies_from_thread(html, url):

    soup = BeautifulSoup(html, 'html.parser')
    replies = soup.find('div', {
        'class': 'thread'
    }).find_all('div', {'class': 'postContainer'})

    data = []
    for i in replies:

        author = i.find('span', {'class': 'postNum'}).find_all('a')
        author = author[1].text if author else False

        image = i.find('a', {'class': 'fileThumb', 'href': True})
        image = image['href'] if image else False

        content = i.find('blockquote', {'class': 'postMessage'})
        if content:
            content = str(content)
            content = content.replace('<wbr/>', '').replace('http', ' http')
            content = re.sub(r'<.*?>', ' ', content)
            content = re.sub(r'&.*?;', ' ', content)
            content = content.replace(' youtube.com', 'youtube.com')
            content = ' '.join(content.split())

            songs = re.findall(r'(https?://\S+)', content)
            soundcloud = [i for i in songs if 'soundcloud' in i.lower()]
            bandcamp = [i for i in songs if 'bandcamp' in i.lower()]
        else:
            soundcloud = []
            bandcamp = []

        data.append({
            'thread': url,
            'author': author,
            'image_url': f'https:{image}' if image else False,
            'content': content,
            'soundcloud': list(set(soundcloud)),
            'bandcamp': list(set(bandcamp))
        })

    return data


def get_songs_replies(catalog_url):

    catalog_html = get_html(catalog_url)
    threads = get_threads_from_catalog(catalog_html)

    songs_threads = [i for i in threads if i['soundcloud'] or i['bandcamp']]
    songs_replies = [
        get_replies_from_thread(get_html(i['url']), i['url'])
        for i in songs_threads
    ]

    return [i for sublist in songs_replies for i in sublist]


def get_songs_urls(songs_replies):

    songs = []
    for i in songs_replies:
        songs.extend(i['soundcloud'])
        songs.extend(i['bandcamp'])

    songs = list(set(songs))
    songs = [
        i.replace('m.', '').replace('www.', '').split('?')[0] for i in songs
    ]

    threads = []
    for i in songs_replies:
        threads.append(i['thread'])
    threads = list(set(threads))

    return songs, threads


if __name__ == '__main__':

    # Files

    CONFIG_JSON = os.path.join(HOME, "config.json")
    try:
        with open(CONFIG_JSON, 'r') as f:
            CONFIG = json.load(f)
    except (IOError, ValueError):
        CONFIG = {'already_queued': []}
        with open(CONFIG_JSON, 'w') as f:
            json.dump(CONFIG, f)

    QBOT_JSON = os.path.join(HOME, "qbot.json")
    try:
        QBOT = json.load(open(QBOT_JSON, 'r'))
    except (IOError, ValueError):
        QBOT = {
            'options': {
                'refresh_schedule': True
            },
            'schedule': {
                'name':
                'mubot',
                'days': [
                    'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
                    'saturday', 'sunday'
                ],
                'hours': []
            },
            'twitter_tokens': {
                'consumer_key': 'find',
                'consumer_secret': 'them',
                'oauth_token': 'on',
                'oauth_secret': 'apps.twitter.com'
            },
            'messages': []
        }

        QBOT['schedule']['hours'] = [
            f"{h:02}:{m:02}" for h in range(10, 24) for m in range(0, 60, 30)
        ]

        with open(QBOT_JSON, 'w') as f:
            json.dump(QBOT, f)

    REPEAT = True
    while REPEAT:

        print(COW)

        # Replies

        songs_replies = get_songs_replies('http://boards.4chan.org/mu/catalog')

        with open(os.path.join(DATAPATH, f'{TIMESTR}.replies.json'), 'w') as f:
            json.dump(songs_replies, f)

        # Songs (soundcloud + bandcamp)

        songs, threads = get_songs_urls(songs_replies)

        with open(os.path.join(DATAPATH, f'{TIMESTR}.songs.json'), 'w') as f:
            json.dump(songs, f)

        with open(os.path.join(DATAPATH, f'{TIMESTR}.threads.json'), 'w') as f:
            json.dump(threads, f)

        # Qbot filling

        found = []
        shuffle(songs)
        for i in songs:
            if i not in CONFIG['already_queued']:
                CONFIG['already_queued'].append(i)
                QBOT['messages'].append({'text': i})
                found.append(i)

        # Save

        with open(os.path.join(HOME, CONFIG_JSON), 'w') as f:
            json.dump(CONFIG, f)

        with open(os.path.join(HOME, QBOT_JSON), 'w') as f:
            json.dump(QBOT, f)

        # Info

        print()
        print('\n'.join(threads))
        print(f'{len(threads)} threads scanned')

        print()
        print('\n'.join(found))
        print(f'{len(found)} songs urls found')

        print(f'\nDone ({round(time.time() - DELTA)}s)')

        # REPEAT

        print()
        TIMER = 0
        DELAY = 60 * 60
        while REPEAT and TIMER < DELAY:
            TIMER += 1
            time.sleep(1)
            sys.stdout.write(f"\rWaiting {DELAY - TIMER} seconds ")
            sys.stdout.flush()
        sys.stdout.write(f"\r{' ' * 36}")
        sys.stdout.flush()

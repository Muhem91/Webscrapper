#!/usr/bin/python
# -*- coding: utf-8 -*-
import getopt
import sys

import urllib.request
import urllib.parse
import urllib.error
from bs4 import BeautifulSoup
import ssl
import json
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time

class Profile:
    def __init__(self, instaUserData):
        self.fullname = instaUserData['full_name']
        self.username = instaUserData['username']
        self.profil_picture_path = instaUserData['profile_pic_url']

    def toObj(self):
        temp = {}
        temp['username'] = self.username
        temp['fullname'] = self.fullname
        temp['profilPicturePath'] = self.profil_picture_path
        return temp

    def __repr__(self) -> str:
        return json.dumps(self.toObj())

class Picture:
    def __init__(self, title, alt_text, picture_page, picture_path):
        self.title = title
        self.alt_text = alt_text
        self.picture_page = picture_page
        self.picture_path = picture_path

    def toObj(self):
        temp = {}
        temp['title'] = self.title
        temp['altText'] = self.alt_text
        temp['picturePath'] = self.picture_path
        return temp

    def __repr__(self) -> str:
        return json.dumps(self.toObj())

class InstagramImageScraper:

    def __init__(self):
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        self.debug = False

        self.hastagUrl = 'https://www.instagram.com/explore/tags/%s/'
        self.profilUrl = 'https://www.instagram.com/%s/'
        self.pictureUrl = 'https://www.instagram.com/p/%s/'

    def getSharedData(self, url):
        html = urllib.request.urlopen(url, context=self.ctx).read()
        soup = BeautifulSoup(html, 'html.parser')
        script = soup.find('script', text=lambda t:
            t.startswith('window._sharedData'))

        return script


    def getHashtags(self, hashtag):
        url = self.hastagUrl % hashtag
        script = self.getSharedData(url)

        page_json = script.text.split(' = ', 1)[1].rstrip(';')
        data = json.loads(page_json)
        print(data)

    def getProfile(self, instagramName):
        url = self.profilUrl % instagramName
        script = self.getSharedData(url)
        if script:
            page_json = script.text.split(' = ', 1)[1].rstrip(';')
            data = json.loads(page_json)
            userData = data['entry_data']['ProfilePage'][0]['graphql']['user']
            return Profile(userData)
        else:
            print('No Data found')

    def downloadProfilPicturesInFile(self, username):
        url = self.profilUrl % username
        browser = webdriver.Chrome('./chromedriver.exe')
        # open Page in browser
        browser.get(url)
        time.sleep(3)

        data = {}
        data['profile'] = self.getProfile(username).toObj()
        data['pictures'] = []
        data['errorAt'] = []

        # to hide the login panel for guests after some scroll
        browser.execute_script("let s = document.createElement('style');" +
                               "s.setAttribute('type', 'text/css');" +
                               "s.setAttribute('rel', 'stylesheet');" +
                               "s.innerText = 'div[role=\"presentation\"] { display: none; }';" +
                               "let head = document.querySelectorAll('head')[0];" +
                               "head.append(s);")

        # execute script to scroll down the page
        scrollHeight = 0
        lastPictureY = 0
        finish = False
        previousI = 0
        while not finish:
            # newLength = browser.execute_script("window.scrollTo(0, document.body.scrollHeight);return document.body.scrollHeight;")
            if True:
                allPictures = browser.find_elements_by_css_selector('a[href*=\'/p/\']')
                newPictures = list(filter(lambda item: item.location['y'] > lastPictureY, allPictures))

                total = previousI + len(newPictures)
                for i, link in enumerate(newPictures, start=1):
                    print('\rProcess: %d von %d' % (previousI + i, total), end='')

                    # if there is a open dialog, close it again
                    dialog = browser.find_elements_by_css_selector('div[role="dialog"]')
                    if dialog:
                        ActionChains(browser).send_keys(Keys.ESCAPE).perform()

                    # scroll to the image to click on it and open the dialog
                    browser.execute_script('window.scrollTo(%d, %d);' % (link.location['x'], link.location['y'] - 200))

                    try:
                        # link to the page with this picture and full comments
                        picture_page = link.get_attribute('href')

                        img = link.find_elements_by_tag_name('img')
                        alt = ''
                        picture_src = ''
                        if img:
                            alt = img[0].get_attribute('alt')
                            picture_src = img[0].get_attribute('src')
                        link.click()
                        time.sleep(1)  # just wait a second

                        # get Titel of image --> first comment in picture
                        dialog = browser.find_elements_by_css_selector('div[role="dialog"]')[0]
                        firstItem = dialog.find_elements_by_css_selector('ul li[role="menuitem"]')[0]
                        title = firstItem.find_elements_by_css_selector('div > div:last-child > span')[0].text

                        # close dialog
                        ActionChains(browser).send_keys(Keys.ESCAPE).perform()
                        data['pictures'].append(Picture(title, alt, picture_page, picture_src).toObj())
                        time.sleep(1)  # Just wait a moment again to close the dialog

                        lastPictureY = link.location['y']
                    except Exception as e:
                        href = link.get_attribute('href')
                        #print(
                        #    'Es ist ein Fehler aufgetreten bei %s. Schleife wird mit nächstem Bild fortgesetzt.' % href)
                        data['errorAt'].append(href)
                        browser.save_screenshot('./selenium/browser_error_picture-%d.png' % i)
                        eingabe = input('\nEs ist ein Fehler aufgetreten. Weitermachen? [j/n]')
                        if eingabe in ['j', 'J', 'ja', 'Ja']:
                            continue
                        else:
                            finish = True
                            break
                print()
                previousI = total
                if self.debug:
                    break
            else:
                print('Seite fertig geladen. Json wird erstellt....')
                break

        print()
        browser.quit()
        filename = './dist/%s.json' % username

        with open(filename, 'w') as outfile:
            json.dump(data, outfile, indent=4)
        print('%s erstellt.' % filename)



def main(argv):
    username = ''
    hashtag = ''

    scraper = InstagramImageScraper()

    try:
        opts, args = getopt.getopt(argv, 'hp:d:t:', ['profile=', 'download=', 'hashtag='])
    except getopt.GetoptError:
        print('Es ist ein Fehler aufgetreten. Versuchen Sie es später erneut oder wenden Sie sich an den Admin.')
        sys.exit(2)

    if len(args) + len(opts) == 0:
        print('Fehlerhafter Aufruf. Tippe -h für Hilfe:')
        print('scraper.py -h')
        sys.exit(1)

    for opt, arg in opts:
        if opt == '-h':
            print('Wenn Sie das Profil eines Benutzers sehen wollen, dann geben Sie -p <username> ein.')
            print('Um alle Bilder eines Profils in eine json zu speichern, geben Sie -d <username> ein.')
            #print('Um alle Bilder zu einem bestimmten Hashtag in eine json zu speichern, geben Sie -t <hashtag> ein.')
            print('z.B. scraper.py -d <username>')
            sys.exit()
        elif opt in ('-p', '--profile'):
            username = arg
            profile = scraper.getProfile(username)
            print(profile)
        elif opt in ('-d', '--download'):
            username = arg
            scraper.downloadProfilPicturesInFile(username)
        elif opt in ('-t', '--hashtag'):
            hashtag = arg
            scraper.getHashtags(hashtag)


if __name__ == "__main__":
    main(sys.argv[1:])

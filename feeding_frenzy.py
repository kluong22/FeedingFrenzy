# -*- encoding: utf-8 -*-
from __future__ import print_function
import httplib2
import urllib2
from bs4 import BeautifulSoup
import os
import re
import json
import requests

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
from oauth2client.service_account import ServiceAccountCredentials

import datetime

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = 'cred.json'
APPLICATION_NAME = 'Feeding Frenzy'
lunchCalendar = "qualtrics.com_f96mbo5mf9scisc60p1hi05qb8@group.calendar.google.com"
minTimeFormat = "%Y-%m-%dT00:00:00-07:00"
maxTimeFormat = "%Y-%m-%dT01:00:00-07:00"
webhook_url = 'https://hooks.slack.com/services/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'

def get_google_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    credential_dir = os.getcwd()
    credential_path = os.path.join(credential_dir,
                                   'google-calendar-cred.json')
    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def service_account_credentials():
    """ For use if/when this script is authorized to access the calendar without user permission

    """
    scopes = ['https://www.googleapis.com/auth/calendar.readonly']
    credential_dir = os.getcwd()
    credential_path = os.path.join(credential_dir, 'service_account_creds.json')
    credentials = ServiceAccountCredentials.from_json_keyfile_name(credential_path, scopes=scopes)
    return credentials

def get_web_page(url):
    try:
        page = urllib2.urlopen(url)
    except ValueError:
        page = urllib2.urlopen("https://" + url)
    soup = BeautifulSoup(page, "html.parser")
    return soup

def get_image(soup):
    div = soup.find_all("div", {"id" : "product-image-and-chef-row"})
    foodPic = div[0].find_all("img", alt = True)
    return ("https:" + foodPic[0]['src'])

def get_description(soup):
    div = soup.find_all("div", {"id" : "product-description-row"})
    food_text = div[0].find_all("p")
    return (food_text[0].get_text())

def get_rating(soup):
    div = soup.find_all("div", {"id" : "product-description-row"})
    food_rating = soup.find_all("meta", {"itemprop" : "ratingValue"})
    if food_rating:
        return ("rating: " + food_rating[0]['content'] + "/5")
    return "rating: " + "?/5"

def get_food_list(url, weekday):
    if (url == None):
        return None
    soup = get_web_page(url)
    days = soup.find_all("span", {"class" : "date-summary"})
    index = -1
    for day in days:
        if weekday in day.get_text():
            index = days.index(day)
    if (index == -1):
        return None
    else:
        menu_list = soup.find_all("div", {"class" : "menu-plan-items"})
        iterFood = iter(menu_list[index].find_all("a"))
        next(iterFood)
        menu = {"attachments" : []}
        for food in iterFood:
            food_entry = {}
            link = food['href']
            soup = get_web_page(link)
            food_entry["fallback"] = food.get_text()
            food_entry["title_link"] = link
            food_entry["title"] = food.get_text()
            food_entry["image_url"] = get_image(soup)
            food_entry["text"] = get_description(soup)
            food_entry["footer"] = get_rating(soup)
            menu["attachments"].append(food_entry)
        return menu

def get_day(soup, weekday):
    days = soup.find_all("span", {"class" : "date-summary"})
    for day in days:
        if weekday in day.get_text():
            index = days.index(day)
            food = day.find_all("div", {"class": "menu-plan-items"})
            children = food.findChildren()
            for child in children:
                print(child)

def get_menu_and_day():
    """
    Returns the day of the week and the menu for that day, or None if no menu exists
    """
    credentials = get_google_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)
    now = datetime.datetime.now()
    timeMin = now.strftime(minTimeFormat)
    timeMax = now.strftime(maxTimeFormat)

    """ For testing
    now = datetime.datetime.fromtimestamp(1503309600.0)
    timeMin = '2017-08-21T00:00:00-07:00'
    timeMax = '2017-08-21T01:00:00-07:00'
    """

    eventsResult = service.events().list(
        calendarId=lunchCalendar, timeMax=timeMax, timeMin=timeMin).execute()
    events = eventsResult.get('items', [])
    data = None
    pizza_day = False
    if events:
        for event in events:
          if 'description' in event and "lishfood" in event['description']:
              pattern = re.compile("www.lishfood.com/menu_plans/\w+/print")
              data = event['description']
              pizza_day = False
              return now.strftime("%A"), pattern.search(data).group(), pizza_day
          elif now.strftime("%A") == "Monday" and 'summary' in event:
              data = event['summary']
              pizza_day = True
    return now.strftime("%A"), data, pizza_day

def post_to_slack(menu, pizza_day):
    """
    Posts the menu of the day to slack, or an inspirational message to inspire people to go out and find food.
    """
    data = None
    if menu == None:
        slack_message = "There is no lunch in the office today ☹️."
        response = requests.get("http://quotes.rest/qod.json?category=inspire")
        if response.status_code == 200:
            json_response = json.loads(response.text)
            slack_message += "\n But here's an inspirational quote to get you through the rest of the day:\n"
            slack_message += '_{}_'.format(json_response['contents']['quotes'][0]['quote'].encode("utf8"))
        data = json.dumps({'text': slack_message})
    elif pizza_day:
        slack_message = "Today is pizza day! Pizza is from " + menu + "."
        data = json.dumps({'text': slack_message})
    else:
        menu['text'] = "Here is today's lunch:\n\n"
        data = json.dumps(menu)
    response = requests.post(
        webhook_url, data,
        headers={'Content-Type': 'application/json'}
    )

def main():
    day, data, pizza_day = get_menu_and_day()
    menu = None
    if pizza_day:
        menu = data
    else:
        menu = get_food_list(data, day)
    post_to_slack(menu, pizza_day)

if __name__ == '__main__':
    main()

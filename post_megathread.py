#!/usr/bin/env python3

import requests
import re
import jinja2 as j2
import argparse
import praw
import json
import datetime


class WatchType:
    def __init__(self, no=0, type="Severe Thunderstorm", pds=False, **kwargs):
        self.no = no
        self.type = type
        self.pds = pds
        self.area = kwargs.get('area', [])
        self.threats = kwargs.get('threats', [])
        self.url = 'https://www.spc.noaa.gov/products/watch/ww' + self.no.zfill(4) + '.html' 

class OutlookType:
    now=datetime.datetime.now()
    def __init__(self, outlookday=1, risk="", yyyymmdd=now.strftime("%Y%m%d"), time_utc="", summary_text=""):
        self.day = outlookday
        self.risk = risk
        self.yyyymmdd = yyyymmdd
        self.time_utc = time_utc
        self.summary = summary_text
        self.url = "https://www.spc.noaa.gov/products/outlook/day" + str(self.day) + "otlk.html"
        if self.risk == "Enhanced":
            self.arisk = "an " + self.risk
        else:
            self.arisk = "a " + self.risk


def check_risks(fn):
    with open(fn) as fp:
        outlooks=[]
        day=1
        while True:
            line = fp.readline()

            if not line:
                break

            if "Forecast Risk of Severe Storms:" in line:
                risk=line
                risk=risk.replace("Risk","")
                risk=re.sub(r'^.*?>', '', risk)
                risk=re.sub(r'<.*?$', '', risk)
                risk=re.sub(r'\s+', '', risk)
                outlooks.append(OutlookType(risk=risk,outlookday=day))
                day+=1

        return outlooks

def populate_risks(outlooks):
    return outlooks

def check_watches(fn):
    with open(fn) as fp:
        watches=[]
        while True:
            line = fp.readline()

            if not line:
                break
            if '<div align="left">' in line:
                for _ in range(4):
                    next(fp) #Skip 4 lines to get to the good stuff
                line=fp.readline()
                x=re.split("[<>]", line)
                if "Particularly Dangerous Situation" in line:
                    watchinfo=x[8]
                    pds=True
                else:
                    watchinfo=x[4]
                    pds=False
                watchno=re.split("#", watchinfo)
                watchsp=re.split(" Watch", watchinfo)
                watches.append(WatchType(no=watchno[1],type=watchsp[0],pds=pds))

        return watches

def populate_watches(watches):
    print(len(watches))
    for watch in watches:

        fn_watch="watch" + watch.no.zfill(4) + ".txt"
        print("Opening ",fn_watch)
        if args.gotime:
            res = requests.get(watch.url)
            if res.status_code != 200:
                print('WARNING: potentially unsuccessful HTTP status code: ', res.status_code)
            print(res.text, file=open(fn_watch, 'w'))
        else:
            print('Running in debug mode; specify argument "--gotime" to run the real deal')
        with open(fn_watch) as fp:
            while True:
                line = fp.readline()

                if not line:
                    break

                # We need to check that watch.area and watch.threats are empty,
                # because the watch text appears twice on the page and we don't want to repeat ourselves
                if "Watch for portions of" in line and not watch.area:
                    line=fp.readline()
                    while line.strip(): 
                        # Add a semicolon unless the line is indented, indicating it continues previous area line
                        if re.search(r'^      ', line ):
                            watch.area[-1] = watch.area[-1] + line.strip()
                        else:
                            watch.area.append(line.strip())
                        line=fp.readline()

                if "* Primary threats include..." in line and not watch.threats:
                    line=fp.readline()
                    while line.strip():
                        # If line is indented, this indicates it continues previous threat line
                        if re.search(r'^      ', line ):
                            watch.threats[-1] = watch.threats[-1] + line.strip()
                        else:
                            watch.threats.append(line.strip())
                        line=fp.readline()

        if watch.pds:
            print("* [**Particularly Dangerous Situation (PDS)** " + watch.type + " Watch " + watch.no + "](" + watch.url + "): portions of")
        else:
            print("* [" + watch.type + " Watch " + watch.no + "](" + watch.url + "): portions of")
        print(watch.area)
        print("\nPrimary threats include...")
        print(watch.threats)

    return watches

def post(subr,title,template_file,outlook,watches,post):
    credentials = 'client_secrets.json'
    with open(credentials) as f:
        creds = json.load(f)

    reddit = praw.Reddit(client_id=creds['client_id'],
                         client_secret=creds['client_secret'],
                         user_agent=creds['user_agent'],
                         redirect_uri=creds['redirect_uri'],
                         refresh_token=creds['refresh_token'])

    subreddit = reddit.subreddit(subr) # Initialize the subreddit to a variable
    reddit.validate_on_submit = True

    now=datetime.datetime.now()

    # Load and substitute jinja template
    templateLoader = j2.FileSystemLoader(searchpath="./")
    templateEnv = j2.Environment(loader=templateLoader)
    template = templateEnv.get_template(template_file)

    #Define summary text and watches text
    watches_text=[]
    for watch in watches:
        if watch.pds:
            watches_text.append("* [**Particularly Dangerous Situation (PDS)** " + watch.type + " Watch " + watch.no + "](" + watch.url + "): portions of")
        else:
            watches_text.append("* [" + watch.type + " Watch " + watch.no + "](" + watch.url + "): portions of")
        watches_text.append(watch.area)
        watches_text.append("\nPrimary threats include...")
        watches_text.append(watch.threats)

    if not watches_text:
        watches_text="* *None in effect*"


    selftext = template.render(risk_level=outlook.risk,arisk=outlook.arisk,num_watches=len(watches),day_of_week=now.strftime("%A"),month=now.strftime("%B"),dd=outlook.yyyymmdd[-2:],yyyy=outlook.yyyymmdd[:4],watches_text=watches_text)

    if not title:
        title="Day " + str(outlook.day) + " severe weather outlook for " + now.strftime("%A") + ", " + now.strftime("%B") + " " + outlook.yyyymmdd[-2:] +", " + outlook.yyyymmdd[:4]

    if post:
        print("Submitting text post to reddit:")
    else:
        print("This is what would be posted to reddit:")
    print("Subreddit: ",subr)
    print("Title: ",title)
    print("Text: ")
    print(selftext)
    if post:
        submission=subreddit.submit(title,selftext=selftext)
        return submission

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--gotime', action='store_true', help='"gotime" should be specified to actively run the script; otherwise it will be run in debug mode on the fixed input files in this directory')
    parser.add_argument('--post', action='store_true', help='"post" should be specified to post to reddit; this will work in debug mode (will post to /r/wazoheat) or gotime mode (will post live to /r/weather).')
    args = parser.parse_args()

    if args.gotime:
        fn_outlooks="outlooks.txt"
        fn_watches="watches.txt"
        res = requests.get('https://www.spc.noaa.gov/products/outlook/')
        if res.status_code != 200:
            print('WARNING: potentially unsuccessful HTTP status code: ', res.status_code)
        print(res.text, file=open(fn_outlooks, 'w'))
        res = requests.get('https://www.spc.noaa.gov/products/watch/')
        if res.status_code != 200:
            print('WARNING: potentially unsuccessful HTTP status code: ', res.status_code)
        print(res.text, file=open(fn_watches, 'w'))

    else:
        print('Running in debug mode; specify argument "--gotime" to run the real deal')
        fn_outlooks="outlooks_debug.txt"
        fn_watches="watches_debug.txt"

#Check general severe risk for Day 1
    outlooks=check_risks(fn_outlooks)

#Check for active watches, grab watch info, populate watch objects
    watches=check_watches(fn_watches)

    if watches:
        watches=populate_watches(watches)
        print("Watches in effect:")
        for watch in watches:
            print(watch.type + " Watch " + watch.no)
            if watch.pds:
                print("PARTICULARLY DANGEROUS SITUATION")
            print("")
    else:
        print("No watches in effect")

    submissions=[]
    for outlook in outlooks:
        print("Day " + str(outlook.day) + " outlook: " + outlook.risk)
        risk_post_levels = {'Enhanced', 'Moderate', 'High'}
        if outlook.risk in risk_post_levels:
            fn_outlook="day" + str(outlook.day) + "outlook.txt"
            if args.gotime:
                res = requests.get(outlook.url)
                if res.status_code != 200:
                    print('WARNING: potentially unsuccessful HTTP status code: ', res.status_code)
                print(res.text, file=open(fn_outlook, 'w'))
                if res.status_code != 200:
                    print('WARNING: potentially unsuccessful HTTP status code: ', res.status_code)

            submissions.append(post("wazoheat","","jinja_template.md",outlook,watches,args.post))

    if submissions:
        print("Successfully posted to reddit")
        for submission in submissions:
            print("Post Title:",submission.title)
            print("Post ID:",submission.id)
            print("Post URL:",submission.url)
    
    


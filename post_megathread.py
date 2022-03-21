#!/usr/bin/env python3

import requests
import re
import jinja2 as j2
import argparse
import praw
import json
import datetime
import os

class WatchType:
    def __init__(self, no=0, type="Severe Thunderstorm", pds=False, **kwargs):
        self.no = no
        self.type = type
        self.pds = pds
        self.area = kwargs.get('area', [])
        self.threats = kwargs.get('threats', [])
        self.url = 'https://www.spc.noaa.gov/products/watch/ww' + self.no.zfill(4) + '.html'
        self.easyurl = ""

class OutlookType:
    now=datetime.datetime.now()
    now_utc=datetime.datetime.utcnow()
    def __init__(self, outlookday=1, risk="", valid="", yyyymmdd=now.strftime("%Y%m%d"), yyyymmdd_utc=now_utc.strftime("%Y%m%d"), time_utc="", time_cdt="", summary_text="", **kwargs):
        self.day = outlookday
        self.risk = risk
        self.valid = valid
        self.yyyymmdd = yyyymmdd
        self.yyyymmdd_utc = yyyymmdd_utc
        self.time_utc = time_utc
        self.time_cdt = time_cdt
        self.summary = summary_text
        self.url = "https://www.spc.noaa.gov/products/outlook/day" + str(self.day) + "otlk.html"
        self.easyurl = ""
        if self.risk == "Enhanced":
            self.arisk = "an " + self.risk
        else:
            self.arisk = "a " + self.risk
        self.prev = kwargs.get('prev', [])


def check_risks(fn):
    with open(fn) as fp:
        outlooks=[]
        day=1
        while True:
            line = fp.readline()

            if not line:
                break

            times=["2000","1630","1300","1200","0100"]
            if "Forecast Risk of Severe Storms:" in line:
                risk=line
                risk=risk.replace("Risk","")
                risk=re.sub(r'^.*?>', '', risk)
                risk=re.sub(r'<.*?$', '', risk)
                risk=re.sub(r'\s+', '', risk)
                outlooks.append(OutlookType(risk=risk,outlookday=day)) 
                # If 0100z outlook does not exist, then we need to look at yesterday
                # Yes I am aware of how ugly this logic is...
                testurl="https://www.spc.noaa.gov/products/outlook/archive/" + outlooks[-1].yyyymmdd_utc[:4] + "/day" + str(day) + "otlk_" + outlooks[-1].yyyymmdd_utc + "_0100.html"
                res = requests.get(testurl)
                if res.status_code == 404:
                    now_utc=datetime.datetime.utcnow()
                    yesterday_utc=now_utc - datetime.timedelta(days = 1)
                    outlooks[-1].yyyymmdd_utc=yesterday_utc.strftime("%Y%m%d")
                print(outlooks[-1].yyyymmdd)
                print(outlooks[-1].yyyymmdd_utc)
                yyyy=outlooks[-1].yyyymmdd_utc[:4]
                mm=outlooks[-1].yyyymmdd_utc[4:6]
                dd=outlooks[-1].yyyymmdd_utc[6:]
                for time in times:
                    testurl="https://www.spc.noaa.gov/products/outlook/archive/" + yyyy + "/day" + str(day) + "otlk_" + outlooks[-1].yyyymmdd_utc + "_" + time + ".html"
                    res = requests.get(testurl)
                    if res.status_code == 200:
                        outlooks[-1].easyurl=testurl
                        outlooks[-1].valid=time
                        break
                date_time_str = outlooks[-1].yyyymmdd_utc + outlooks[-1].valid + " +0000"
                outlooks[-1].time_utc = datetime.datetime.strptime(date_time_str, '%Y%m%d%H%M %z')
                outlooks[-1].time_cdt=outlooks[-1].time_utc - datetime.timedelta (hours=5)
                print(outlooks[-1].time_utc)
                print(outlooks[-1].time_cdt)
#                day+=1
                break

        return outlooks

def populate_risks(outlooks):
    for outlook in outlooks:

        fn_outlook="day" + str(outlook.day) + "outlook.txt"
        if args.gotime:
            res = requests.get(outlook.easyurl)
            if res.status_code != 200:
                print('WARNING: potentially unsuccessful HTTP status code: ', res.status_code)
            print(res.text, file=open(fn_outlook, 'w'))
        else:
            print('Running in debug mode; specify argument "--gotime" to run the real deal')
        with open(fn_outlook) as fp:
            while True:
                line = fp.readline()

                if not line:
                    break

                if "...SUMMARY..." in line:
                    line=fp.readline()
                    outlook.summary=line.strip()
                    line=fp.readline()
                    while line.strip():
                        outlook.summary = outlook.summary + " " + line.strip()
                        line=fp.readline()
#                if '<tr><td align="center" class="zz" nowrap>' in line:
#                    utc=line
#                    utc=utc.replace("Risk","")
#                    utc=utc.sub(r'^.*?>', '', risk)
#                    outlook.time_utc=utc

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
    for watch in watches:

        fn_watch="watch" + watch.no.zfill(4) + ".txt"
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
                        # If the line is indented, this indicates it continues previous area line
                        if re.search(r'^      ', line ):
                            watch.area[-1] = watch.area[-1] + " " + line.strip()
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

    return watches

def post(subr,title,location,template_file,outlook,watches,post,update):

    #Open credentials file and populate the praw object and various settings for posting to reddit
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

    # Check for 'other_notes.txt', the file that will be appended as-is near the end of the post

    other_notes=''
    if os.path.isfile('other_notes.txt'):
        with open('other_notes.txt', "r") as text_file:
            other_notes = text_file.read()

    now=datetime.datetime.now()

    # Load and substitute jinja template
    templateLoader = j2.FileSystemLoader(searchpath="./")
    templateEnv = j2.Environment(loader=templateLoader)
    template = templateEnv.get_template(template_file)

    #Define summary text and watches text
    watches_text=[]
    for watch in watches:
        if watch.pds:
            watches_text.append(''.join("[**Particularly Dangerous Situation (PDS)** " + watch.type + " Watch " + str(watch.no) + "](" + watch.url + "): portions of"))
        else:
            watches_text.append(''.join("[" + watch.type + " Watch " + str(watch.no) + "](" + watch.url + "): portions of"))
        watches_text.append(";\n".join(watch.area))
        watches_text.append("\nPrimary threats include...")
        watches_text.append(";\n".join(watch.threats))
        watches_text.append("\n----")

    if not watches_text:
        watches_text=[ "* *None in effect*" ]

    selftext = template.render(risk_level=outlook.risk,arisk=outlook.arisk,num_watches=len(watches),day_of_week=now.strftime("%A"),month=now.strftime("%B"),dd=outlook.yyyymmdd_utc[-2:],mm=outlook.yyyymmdd_utc[-4:-2],yyyy=outlook.yyyymmdd_utc[:4],yyyymmdd=outlook.yyyymmdd_utc,watches_text="\n".join(watches_text),hhmm=outlook.valid,other_notes=other_notes,time_cdt=outlook.time_cdt.strftime("%H:%M"),summary_text=outlook.summary,post_id=update)

    if not title and not update:
        title="[Megathread] " + location + " Severe Weather Discussion, " + now.strftime("%A") + ", " + now.strftime("%B") + " " + outlook.yyyymmdd[-2:] +", " + outlook.yyyymmdd[:4]

    if post:
        print("Submitting text post to reddit:")
    else:
        print("This is what would be posted to reddit:")
    print("Subreddit: ",subr)
    print("Title: ",title)
    print("Text: ")
    print(selftext)
    if post:
        if update:
            submission = reddit.submission(id=update)
            submission = submission.edit(selftext)
        else:
            submission=subreddit.submit(title,selftext=selftext)

        return submission

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--gotime', action='store_true', help='"gotime" should be specified to actively run the script; otherwise it will be run in debug mode on the fixed input files in this directory')
    parser.add_argument('--post', action='store_true', help='"post" should be specified to post to reddit; this will work in debug mode or gotime mode')
    parser.add_argument('--update', help='"update" should provide the base-32 id of an existing post to update; if --post is not specified, this argument does nothing')
    parser.add_argument('--location', type=str, help='"location" should describe the location of the specific severe weather threat for the title of the post; if --post is not specified or if --update *is* specified, this argument does nothing')
    parser.add_argument('--sub', type=str, help='"sub" specifies the subreddit to submit to; if --post is not specified, this argument does nothing')

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
#        print("Watches in effect:")
#        for watch in watches:
#            print(watch.type + " Watch " + watch.no)
#            if watch.pds:
#                print("PARTICULARLY DANGEROUS SITUATION")
#            print("")
    else:
        print("No watches in effect")

    submissions=[]
#    for outlook in outlooks:
#        print("Day " + str(outlook.day) + " outlook: " + outlook.risk)
#        risk_post_levels = {'Enhanced', 'Moderate', 'High'}
#        if outlook.risk in risk_post_levels:
#            fn_outlook="day" + str(outlook.day) + "outlook.txt"
#            if args.gotime:
#                res = requests.get(outlook.url)
#                if res.status_code != 200:
#                    print('WARNING: potentially unsuccessful HTTP status code: ', res.status_code)
#                print(res.text, file=open(fn_outlook, 'w'))
#                if res.status_code != 200:
#                    print('WARNING: potentially unsuccessful HTTP status code: ', res.status_code)
#
#            submissions.append(post("weatherbot5000","","jinja_template.md",outlook,watches,args.post))

    if outlooks:
        outlooks=populate_risks(outlooks)

    if args.sub is None:
        sub="weatherbot5000"
    else:
        sub=args.sub
    submissions.append(post(sub,"",args.location,"jinja_template.md",outlooks[0],watches,args.post,args.update))
    if submissions[0] is not None:
        print("Successfully posted to reddit")
        for submission in submissions:
            print("Post Title:",submission.title)
            print("Post ID:",submission.id)
            print("Post URL:",submission.url)


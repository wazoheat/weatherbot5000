#!/usr/bin/env python3

import requests
import re
import jinja2 as j2
import argparse
import praw
import json



class WatchType:
    def __init__(self, no=0, type="Severe Thunderstorm", pds=False, area="", threats=""):
        self.no = no
        self.type = type
        self.pds = pds
        self.area = area
        self.threats = threats

def check_risk(fn):
    with open(fn) as fp:
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
                return risk

#        Forecast Risk of Severe Storms: <span class="enhanced">Enhanced Risk</span>

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

def post(subr,title,template_file,risk_level,watches,post):
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

    templateLoader = j2.FileSystemLoader(searchpath="./")
    templateEnv = j2.Environment(loader=templateLoader)
    template = templateEnv.get_template(template_file)
    selftext = template.render(risk_level=risk_level,num_watches=len(watches))

    if not title:
        title="Severe weather outlook for TEST" 

    if post:
        print("Submitting text post to reddit:")
    else:
        print("This is what would be posted to reddit:")
    print("Subreddit: ",subr)
    print("Title: ",title)
    print("Text: ")
    print(selftext)
    if post:
        subreddit.submit(title,selftext=selftext)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--gotime', action='store_true', help='"gotime" should be specified to actively run the script; otherwise it will be run in debug mode on the fixed input files in this directory')
    parser.add_argument('--post', action='store_true', help='"post" should be specified to post to reddit; this will work in debug mode (will post to /r/wazoheat) or gotime mode (will post live to /r/weather).')
    args = parser.parse_args()

    if args.gotime:
        fn_outlooks="outlooks.txt"
        fn_watches="watches.txt"
        res = requests.get('https://www.spc.noaa.gov/products/outlook/')
        print(res.text, file=open(fn_outlooks, 'w'))
        if res.status_code != 200:
            print('WARNING: potentially unsuccessful HTTP status code: ', res.status_code)
        res = requests.get('https://www.spc.noaa.gov/products/watch/')
        print(res.text, file=open(fn_watches, 'w'))
        if res.status_code != 200:
            print('WARNING: potentially unsuccessful HTTP status code: ', res.status_code)

    else:
        print('Running in debug mode; specify argument "--gotime" to run the real deal')
        fn_outlooks="outlooks_debug.txt"
        fn_watches="watches_debug.txt"

#Check general severe risk for Day 1
    risk=check_risk(fn_outlooks)
            
    print("Day 1 risk level is ",risk)

#Check for active watches
    watches=check_watches(fn_watches)

    if not watches:
        print("No watches in effect")
    else:
        print("Watches in effect:")
        for watch in watches:
            print(watch.type + " Watch " + watch.no)
            if watch.pds:
                print("PARTICULARLY DANGEROUS SITUATION")
            print("")

    post("wazoheat","","jinja_template.md",risk,watches,args.post)

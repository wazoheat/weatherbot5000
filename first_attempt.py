#!/usr/bin/env python3

import requests
import re
import jinja2 as j2
import argparse

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


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--gotime', action='store_true', help='"gotime" should be specified to actively run the script; otherwise it will be run in debug mode on the fixed input files in this directory')
    args = parser.parse_args()

    if args.gotime:
        filename="outlooks.txt"
        res = requests.get('https://www.spc.noaa.gov/products/outlook/')
        print(res.text, file=open(filename, 'w'))
        status_code=res.status_code
        txt=res.text
    else:
        print('Running in debug mode; specify argument "--gotime" to run the real deal')
        filename="outlooks_debug.txt"
        status_code=200

    if status_code != 200:
        print('WARNING: potentially unsuccessful HTTP status code: ', res.status_code)
    else:
        print('HTTP status response OK: ',status_code)

    risk=check_risk(filename)
            
    print("Day 1 risk level is ",risk)


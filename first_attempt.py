#!/usr/bin/env python3

import requests
import re
import jinja2 as j2


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
                break

#        Forecast Risk of Severe Storms: <span class="enhanced">Enhanced Risk</span>


if __name__ == '__main__':
    debug='false'
#    debug='true'

    if debug == "true":
        filename="outlooks_debug.txt"
        status_code=200
    else:
        filename="outlooks.txt"
        res = requests.get('https://www.spc.noaa.gov/products/outlook/')
        print(res.text, file=open(filename, 'w'))
        status_code=res.status_code
        txt=res.text

    if status_code != 200:
        print('WARNING: potentially unsuccessful HTTP status code: ', res.status_code)
    else:
        print('HTTP status response OK: ',status_code)

    risk=check_risk(filename)
            
    print("Day 1 risk level is ",risk)


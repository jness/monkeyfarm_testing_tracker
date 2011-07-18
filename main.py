#!/usr/bin/env python

import os
import argparse
from monkeyfarm.interface import MFInterface, MFAPIKeyRequestHandler
from datetime import datetime, timedelta
from time import mktime, strptime
from configobj import ConfigObj

def get_connection(con_name='default'):
    '''parses your ~/.mf.conf for API key'''
    if not con_name:
        con_name = 'default'

    c = os.path.expanduser('~/.mf.conf')
    if os.path.exists(c):
        config = ConfigObj(c)
    else:
        raise Exception('~/.mf.conf not found')

    for sect in config.sections:
        if sect.startswith('connection:'):
            try:
                assert config[sect].has_key('user'), \
                    "Missing 'user' setting in %s (%s)." % (_file, sect)
                assert config[sect].has_key('api_key'), \
                    "Missing 'api_key' setting in %s (%s)." % (_file, sect)
                assert config[sect].has_key('url'), \
                    "Missing 'url' setting in %s (%s)." % (_file, sect)
            except AssertionError, e:
                raise e

            name = sect.split(':')[1]
            if name == con_name:
                api = {}
                api['api_key'] = config[sect]['api_key']
                api['user'] = config[sect]['user']
                api['url'] = config[sect]['url']
                return (api)
    else:
        return False
    
def connect():
    '''Connects to Monkey Farm'''
    config = get_connection(con_name='default')
    if config:
        rh = MFAPIKeyRequestHandler(config['url'])
        rh.auth(config['user'], config['api_key'])
        hub = MFInterface(request_handler=rh)
        return hub
    else:
        raise Exception('It does not appear you have a ~/.mf.conf')
        
def testing_builds(hub):
    '''return a list of packages in the testing tag'''
    pkgs = hub.tag.get_one('testing', 'ius')['data']['tag']['builds']
    return pkgs

def build_info(hub, build):
    '''gets useful build information'''
    b = {}
    b[build] = {}
    
    req = hub.build.get_one(build, 'ius')
    packager = req['data']['build']['user_label']
    status = req['data']['build']['status_label']
    update_date = req['data']['build']['update_date']
    releases = req['data']['build']['releases']
    
    time_format = "%Y-%m-%d %H:%M:%S"
    date = datetime.fromtimestamp(mktime(strptime(update_date, time_format)))
    
    b[build]['packager'] = packager
    b[build]['date'] = date
    b[build]['status'] = status
    b[build]['releases'] = releases
    return b

def user_email(hub, user):
    email = hub.user.get_one(user)['data']['user']['email']
    return email

def send_email(fromaddr, email, msg):
    '''send a message to user via email'''
    from socket import error
    from smtplib import SMTP
    
    try:
        server = SMTP('localhost')
        server.set_debuglevel(0)
    except error as e:
        return e
    else:
        server.sendmail(fromaddr, email, msg)
        server.quit()
        return 'email sent to %s' % email


def main():
    '''Our main function'''
    
    # Build my Parser with help for user input
    parser = argparse.ArgumentParser()
    parser.add_argument('--days',
                        help='only give builds X days old, where X is --days',
                        required=True)
    args = parser.parse_args()
    
    # connect to monkeyfarm and get all build
    # tagged as testing
    hub = connect()
    testing = testing_builds(hub)
    # set our current datetime 
    now = datetime.now()

    # loop through our builds and append any
    # older than 14 days to dict
    builds = {}    
    for build in testing:
        b = build_info(hub, build)
        delta = (now - b[build]['date'])
        if delta > timedelta(days = int(args.days)):
            
            # add days to build
            b[build]['days'] = delta.days
            
            # simple reference names
            packager = b[build]['packager']
         
            # create a per user dict for notifications
            if builds.has_key(packager):
                builds[packager][build] = b[build]
            else:
                builds[packager] = {}
                builds[packager][build] = b[build]

    # now that we have all our builds we can
    # loop through the users and send notifications
    for user in builds:
        email = user_email(hub, user)
        
        # prepare email for delivery
        fromaddr = 'monkeyfarm@localhost'
        subject = '[MonkeyFarm] build tag as testing over %s days' % args.days
        
        email_header = 'From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n' % (
                        fromaddr, email, subject
                        )
        
        body = str()
        for build in builds[user]:
            b = builds[user][build]
            body = body + 'Build: %s\nDate: %s\nStatus: %s\nReleases: %s\nDays Tagged: %s\n\n' % (
                    build, b['date'], b['status'], ', '.join(b['releases']), b['days']
            )
           
        msg = email_header + body        
        
        # send the email
        mail = send_email(fromaddr, email, msg)
        print mail
        
        
if __name__ == "__main__":
    main()
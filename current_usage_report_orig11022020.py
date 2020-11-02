#!/usr/bin/python3
import os
import sys
import argparse
import paramiko
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date


def get_du_stats(host):

    global df_out
    try:
        #cert = paramiko.RSAKey.from_private_key_file("tkoulech-ohio.pem")
        cert = paramiko.RSAKey.from_private_key_file("tkoulech-ca.pem")
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # print("connecting to {}...".format(host))
        #c.connect( hostname = host, username = "ubuntu", pkey = cert )
        c.connect( hostname = host, username = "ec2-user", pkey = cert )
        # print("connected!!!")
        stdin, stdout, stderr = c.exec_command('df -h')
        df_out = stdout.readlines()[1:]
        c.close()

    except:
        print("Connection to {} Failed!!!".format(host))
        df_out = []

    flagSystem = False
    #TK stream = os.popen('ssh -i "tkoulech-ohio.pem" -o ConnectTimeout=10 ubuntu@{} \'df -h\''.format(host))
    # df_out is empty if connection timed out
    #TK df_out = stream.read().splitlines()[1:]

    pDict[host] = []
    if df_out:
        for p in df_out:
            pArray = p.rstrip().split()
            usage, part = pArray[len(pArray) - 2], pArray[len(pArray) - 1]
            if 80 < int(usage.rstrip('%')) < 89:
                status = 'prewarning'
                flagSystem = True
                prewarnHosts.add(host)
            elif int(usage.rstrip('%')) > 90:
                status = 'warning'
                flagSystem = True
                warnHosts.add(host)
            else:
                status = 'ok'

            # constract a dictionary with 'host' as a key and list of tuples as value
            pDict[host].append((part, usage, status))

    # constract list of OK hosts: ssh didn't fail and they do not have either pre-warning or warning partitions
    if df_out and not flagSystem: okHosts.append(host)
    if not df_out: notreachableHosts.append(host)
    return pDict

def cur_du_all(pDict):
    for h in pDict.keys():
        if pDict[h]:
            print("\t -> Current Dist Usage for {}".format(h))
            for part,usage,status in pDict[h]:
                print('\t', f'{part:30} is at {usage}')
            print("")


def warn_du(pDict):
    text_msg = ''
    for h in pDict.keys():
        if pDict[h]:
            print("\t -> {}: critical disk usage".format(h))
            text_msg += '''\n\t -> {}: critical disk usage'''.format(h)
            for part,usage,status in pDict[h]:
                if status == 'warning':
                    text_msg += '''\n\t {:30} is at {}'''.format(part, usage)
                    print('\t', f'{part:30} is at {usage}')
            print("")
    return text_msg


def prewarn_du(pDict):
    text_msg = ''
    for h in pDict.keys():
        if pDict[h]:
            print("\t -> {}: pre-warning disk usage".format(h))
            text_msg += '''\n\t -> {}: pre-warning disk usag'''.format(h)
            for part,usage,status in pDict[h]:
                if status == 'prewarning':
                    text_msg += '''\n\t {:30} is at {}'''.format(part, usage)
                    print('\t', f'{part:30} is at {usage}')

            print("")
    return text_msg

if __name__ == '__main__':
    okHosts = []
    notreachableHosts = []
    prewarnHosts = set()
    warnHosts = set()
    pDict = {}
    text_msg = ''

    parser = argparse.ArgumentParser(description="Servers list")
    parser.add_argument('-s', '--sspec', dest='sspec', metavar='server_spec', required=True, help='path to a server spec file')
    args = parser.parse_args()
    sspec = args.sspec

    #servers = '/home/ubuntu/monitoring/servers.txt'
    #servers = '/home/ec2-user/scripts/servers.txt'


    # check if 'servers' file exists and valid
    if not os.path.isfile(sspec):
        sys.exit("server's specification file {} is not valid".format(sspec))

    for host in open(sspec).read().splitlines():
        pDict = get_du_stats(host)

    # Report hosts that timed out on ssh
    if notreachableHosts:
        print("***                 Servers are not reachable                 ***")
        text_msg += '''\n\n***                 Servers are not reachable                 ***'''
        for h in notreachableHosts:
            print('\t -> ssh connection timed out on ', h)
            text_msg += '''\n\t -> ssh connection timed out on {}'''.format(host)
        print("")

    # Report hosts in Pre-Warning level
    if prewarnHosts:
        text_msg += '''\n\n*** PRE-WARNING: Servers with partitions at pre-warning level ***'''
        print("*** PRE-WARNING: Servers with partitions at pre-warning level ***")
        text_msg += prewarn_du(pDict)
        print("")

    # Report hosts in Warning level
    if warnHosts:
        print("*** WARNING: Servers with partitions at a critical level ***")
        text_msg += '''\n\n*** WARNING: Servers with partitions at a critical level ***'''
        text_msg += warn_du(pDict)
        print("")

    # current disk usage for all hosts
    print("***                Servers disk usage                    ***")
    cur_du_all(pDict)
    print("")

    # Report hosts that are okay (no pre-warn, warn partitions)
    if okHosts:
        print("***         Servers with normal disk space usage         ***")
        for h in okHosts:
            print('\t', h)

    now = datetime.now()
    current_time = now.strftime("%H%M%S")
    today = date.today()
    current_date = today.strftime("%Y%m%d")

    if warnHosts or prewarnHosts or notreachableHosts:
        s_email = 'tiadevops@gmail.com'
        gmailpassword = 'tiadevops2020'
        r_email = 'tiadevops@gmail.com'
        port = 465  # For SSL
        smtp_server = "smtp.gmail.com"
        msg = MIMEMultipart("alternative")
        msg['Subject'] = f'!!!Alert!!!: Disk usage report {current_date}_{current_time}'
        msg['From'] = 'tiadevops@gmail.com'
        msg['To'] = 'tiadevops@gmail.com'

        # Turn these into plain/html MIMEText objects
        part1 = MIMEText(text_msg, "plain")
        msg.attach(part1)

        # use create_default_context() from the ssl module. This will load the system’s trusted CA certificates,
        # enable host name checking and certificate validation,
        # and try to choose reasonably secure protocol and cipher settings.
        context = ssl.create_default_context()
        # Start an SMTP connection that is secured from the beginning using SMTP_SSL()
        with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
            server.login(s_email, gmailpassword)
            server.sendmail(s_email, r_email, msg.as_string())
        # print(" \n Sent!")

    sys.exit(0)

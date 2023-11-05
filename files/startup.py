import os
from shutil import copyfile
import subprocess
import json
import sys

def cleanup_file(filename):
    """If file exists, delete it"""
    if os.path.isfile(filename):
        os.remove(filename)
    else:
        print(f"{filename} does not exist")

def copy_file_if_not_exists(src, dest):
    """Copy the file if it does not exist at the destination"""
    if os.path.isfile(dest):
        print(f"{dest} does already exist - do nothing")
    else:
        copyfile(src, dest)
        print(f"{dest} copied")

def start_service(servicename):
    """Start a Linux service"""
    print(f"Starting service {servicename}")
    p = subprocess.Popen(['/usr/sbin/service', servicename, 'start'], stdout=subprocess.PIPE)
    p.communicate()
    if p.returncode != 0:
        print(f"Failed to start service {servicename}")

def fix_permissions():
    """ fix the permissions of the bayes folders"""
    paths_to_fix = ['/var/spamassassin/bayesdb', '/root/accounts']
    for path in paths_to_fix:
        p = subprocess.Popen(['chmod', 'a+wr', path, '-R'], stdout=subprocess.PIPE)
        output, err = p.communicate()
        if p.returncode != 0:
            print(f"Failed to fix permissions for {path}")
            print(err)
            print(output)

def start_imap_idle(account):
    """Start the IMAP idle process"""
    print(f"Starting IMAP IDLE for {account['user']}")
    p = subprocess.Popen(['python3', '/root/antispambox.py'], stdout=subprocess.PIPE)
    output, err = p.communicate()
    if p.returncode != 0:
        print(f"Failed IMAP IDLE for {account['user']}")
        print(err)
        print(output)

def check_imap_configuration():
    """Check if the IMAP account has already been configured"""
    try:
        with open("/root/accounts/imap_accounts.json", 'r') as f:
            datastore = json.load(f)
        
        if datastore["antispambox"]["enabled"].lower() != "true":
            print("Antispambox is not enabled - exiting.")
            sys.exit()

        accounts = datastore["antispambox"]["accounts"]
        for account in accounts:
            if account["enabled"].lower() == "true":
                print(f"Account {account['user']} is enabled.")
                start_imap_idle(account)
            else:
                print(f"Account {account['user']} is disabled, skipping.")
    except Exception as e:
        print("ERROR: Unable to read imap_accounts.json.")
        print(e)
        sys.exit()

print("\n\n ******* STARTUP ANTISPAMBOX ******* \n\n")

cleanup_file("/root/.cache/irsd/lock")
copy_file_if_not_exists("/root/imap_accounts.json", "/root/accounts/imap_accounts.json")
fix_permissions()

start_service("rsyslog")
start_service("redis-server")
start_service("rspamd")
start_service("lighttpd")
start_service("cron")

check_imap_configuration()

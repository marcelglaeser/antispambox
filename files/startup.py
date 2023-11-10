import json
import os
import subprocess
import sys
from shutil import copyfile


def cleanup_file(filename):
    """If file exists, delete it"""
    if os.path.exists(filename):
        os.remove(filename)
        print(f"{filename} removed")
    else:
        print(f"{filename} does not exist")


def copy_file_if_not_exists(src, dest):
    """Copy the file if it does not exist at the destination"""
    if not os.path.exists(dest):
        copyfile(src, dest)
        print(f"{src} copied to {dest}")
    else:
        print(f"{dest} already exists - skipped copying")


def start_service(servicename):
    """Start a Linux service"""
    print(f"Starting service {servicename}")
    p = subprocess.run(['/usr/sbin/service', servicename, 'start'])
    if p.returncode != 0:
        print(f"Failed to start service {servicename}")


def fix_permissions():
    """Fix the permissions of the bayes folders"""
    paths_to_fix = ['/var/spamassassin/bayesdb', '/root/accounts']
    for path in paths_to_fix:
        p = subprocess.run(['chmod', 'a+wr', path, '-R'])
        if p.returncode != 0:
            print(f"Failed to fix permissions for {path}")


def start_imap_idle(account):
    """Start the IMAP idle process"""
    print(f"Starting IMAP IDLE for {account['user']}")
    p = subprocess.run(['python3', '/root/antispambox.py'])
    if p.returncode != 0:
        print(f"Failed IMAP IDLE for {account['user']}")


def check_imap_configuration():
    """Check if the IMAP account has already been configured"""
    try:
        with open("/root/accounts/imap_accounts.json", 'r') as f:
            datastore = json.load(f)

            if datastore["antispambox"].get("enabled", "").lower() != "true":
                print("Antispambox is not enabled - exiting.")
                sys.exit()

            accounts = datastore["antispambox"]["accounts"]
            for account in accounts:
                if account.get("enabled", "").lower() == "true":
                    print(f"Account {account.get('user', 'Unknown')} is enabled.")
                    start_imap_idle(account)
                else:
                    print(f"Account {account.get('user', 'Unknown')} is disabled, skipping.")
    except Exception as e:
        print("ERROR: Unable to read imap_accounts.json.")
        print(e)
        sys.exit()


print("\n\n ******* STARTUP ANTISPAMBOX (MULTI-ACCOUNT) ******* \n\n")

cleanup_file("/root/.cache/irsd/lock")
copy_file_if_not_exists("/root/imap_accounts.json", "/root/accounts/imap_accounts.json")
fix_permissions()

services = ["redis-server", "rspamd", "lighttpd", "cron"]
for service in services:
    start_service(service)

check_imap_configuration()

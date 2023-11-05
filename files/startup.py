import os
from shutil import copyfile
import subprocess
import json
import sys

def cleanup_file(filename):
    """If file exists, delete it"""
    if os.path.isfile(filename):
        os.remove(filename)
    else:  ## Show an error ##
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
    print(f"startup service {servicename}")
    p = subprocess.Popen(['/usr/sbin/service', servicename, 'start'], stdout=subprocess.PIPE)
    p.communicate()
    if p.returncode != 0:
        print(f"startup of service {servicename} failed")

def check_imap_configuration():
    """ check if the IMAP accounts have already been configured"""
    try:
        with open("/root/accounts/imap_accounts.json", 'r') as f:
            datastore = json.load(f)
        # Loop through each account configuration
        for account_name, account_config in datastore.items():
            enabled = account_config.get("enabled", "False")
            host = account_config.get("account", {}).get("server", "")
            if enabled.lower() != "true":
                print(f"ERROR: Antispambox configuration for {account_name} is not set to enabled - skipping this account")
                continue
            if host == "imap.example.net":
                print(f"ERROR: No server configured for {account_name} in imap_accounts.json - please configure and restart")
                continue
            print(f"Configuration for {account_name} looks fine.")
    except (IndexError, json.JSONDecodeError) as e:
        print("ERROR: was not able to read imap_accounts.json.")
        print(e)
        sys.exit()

def fix_permissions():
    """ fix the permissions of the rspamd and other necessary folders"""
    # Removed the commented-out lines to clean up the script
    permissions_paths = ['/etc/rspamd/local.d', '/var/spamassassin']
    for path in permissions_paths:
        p = subprocess.Popen(['chmod', 'a+wr', path, '-R'], stdout=subprocess.PIPE)
        (output, err) = p.communicate()
        if p.returncode != 0:
            print(f"chmod failed on {path}")
            print(err)
            print(output)

def download_spamassassin_rules():
    """download the spamassassin rules"""
    # This function has been simplified to call sa-update once
    p = subprocess.Popen(['/usr/bin/sa-update', '--no-gpg', '-v'], stdout=subprocess.PIPE)
    (output, err) = p.communicate()
    if p.returncode not in (0, 1):
        print("ERROR: sa-update failed")
        print(err)
        print(output)

def start_imap_idle():
    """Start the IMAP idle process for each account"""
    # This function will need to be updated to handle multiple accounts
    # Currently it assumes a single process handling all accounts
    p = subprocess.Popen(['python3', '/root/antispambox.py'], stdout=subprocess.PIPE)
    (output, err) = p.communicate()
    # this will usually run endless
    if p.returncode != 0:
        print("ERROR: IMAPIDLE / PUSH / antispambox failed")
        print(err)
        print(output)

# ... the rest of the script remains unchanged ...

print("\n\n *** start of IMAPIDLE / PUSH")
start_imap_idle()

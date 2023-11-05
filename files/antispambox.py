from imapclient import IMAPClient
import subprocess
import json
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from threading import Thread

# configure logging
logger = logging.getLogger("Antispambox")
logger.setLevel(logging.INFO)

# rotate the logfile every 24 hours
handler = TimedRotatingFileHandler('/var/log/antispambox.log', when="H", interval=24, backupCount=5)

# format the logfile (add timestamp etc)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

handler.setFormatter(formatter)
logger.addHandler(handler)

# log to stdout
logger.addHandler(logging.StreamHandler())

# read account information
try:
    with open("/root/accounts/imap_accounts.json", 'r') as f:
        datastore = json.load(f)
except (IndexError, json.JSONDecodeError) as e:
    logger.error("ERROR: was not able to read imap_accounts.json.")
    logger.error(e)
    sys.exit(1)

# Define a function to handle IMAP IDLE and spam scanning for a single account
def handle_account(account_name, account_config):
    HOST = account_config["server"]
    USERNAME = account_config["user"]
    PASSWORD = account_config["password"]
    JUNK = account_config["junk_folder"]
    INPUT = account_config["inbox_folder"]
    HAMTRAIN = account_config["ham_train_folder"]
    SPAMTRAIN = account_config["spam_train_folder"]
    CACHEPATH = "rspamd"

    def scan_spam():
        logger.info(f"Scanning for SPAM with rspamd for account: {account_name}")
        cmd = f'/usr/local/bin/irsd --imaphost {HOST} --imapuser {USERNAME} --imappasswd {PASSWORD} --spaminbox {JUNK} --imapinbox {INPUT} --learnhambox {HAMTRAIN} --learnspambox {SPAMTRAIN} --cachepath {CACHEPATH} --delete --expunge --partialrun 500'
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        output, err = p.communicate()
        if p.returncode != 0:
            logger.error(f"ERROR: sa-update failed for account: {account_name}")
            logger.error(err)
        logger.info(output)

    def login():
        # login to server
        while True:
            try:
                server = IMAPClient(HOST)
                server.login(USERNAME, PASSWORD)
                server.select_folder('INBOX')
                # Start IDLE mode
                server.idle()
                logger.info(f"Connection is now in IDLE mode for account: {account_name}")
            except Exception as e:
                logger.error(f"Failed to connect for account: {account_name} - trying again")
                logger.error(e)
                continue
            return server

    def logoff(server):
        server.idle_done()
        logger.info(f"IDLE mode done for account: {account_name}")
        server.logout()

    def pushing(server):
        """run IMAP idle until an exception (like no response) happens"""
        count = 0
        while True:
            try:
                # Wait for up to 30 seconds for an IDLE response
                responses = server.idle_check(timeout=29)

                if responses:
                    logger.info(f"Response for account {account_name}: {responses}")
                    count = 0
                    scan_spam()
                else:
                    logger.info(f"No responses for account {account_name}")
                    count += 1
                 
                if count > 25:
                    logger.info(f"No responses from Server for account {account_name} - Scan for Spam, then Restart")
                    scan_spam()
                    count = 0
                    raise Exception("No response")

            except KeyboardInterrupt:
                break

            except Exception as e:
                logger.error(f"Push error for account: {account_name}")
                count = 0
                break

    # Start the IMAP IDLE process
    try:
        server = login()
        pushing(server)
        logoff(server)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Exception for account: {account_name}")
        logger.error(e)
    finally:
        logoff(server)

# Start a thread for each account
threads = []
for account_name, account_config in datastore.items():
    if account_config.get("enabled", "False").lower() == "true":
        t = Thread(target=handle_account, args=(account_name, account_config))
        t.start()
        threads.append(t)
    else:
        logger.info(f"Skipping disabled account: {account_name}")

# Wait for all threads to finish
for t in threads:
    t.join()

logger.info("Antispambox script exited")

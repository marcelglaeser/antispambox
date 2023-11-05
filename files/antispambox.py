from imapclient import IMAPClient
import subprocess
import json
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from threading import Thread

# Configure logging
logger = logging.getLogger("Antispambox")
logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler('/var/log/antispambox.log', when="H", interval=24, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.addHandler(logging.StreamHandler())

# Read account information
try:
    with open("/root/accounts/imap_accounts.json", 'r') as f:
        datastore = json.load(f)
except (IndexError, json.JSONDecodeError) as e:
    logger.error("ERROR: Unable to read imap_accounts.json.")
    logger.error(e)
    sys.exit(1)

# Define a function to handle IMAP IDLE and spam scanning for a single account
def handle_account(account):
    HOST = account["server"]
    USERNAME = account["user"]
    PASSWORD = account["password"]
    JUNK = account["junk_folder"]
    INPUT = account["inbox_folder"]
    HAMTRAIN = account["ham_train_folder"]
    SPAMTRAIN = account["spam_train_folder"]

    def scan_spam():
        logger.info(f"Scanning for SPAM with rspamd for account: {USERNAME}")
        cmd = f'/usr/local/bin/irsd --imaphost {HOST} --imapuser {USERNAME} --imappasswd {PASSWORD} --spaminbox {JUNK} --imapinbox {INPUT} --learnhambox {HAMTRAIN} --learnspambox {SPAMTRAIN} --cachepath rspamd --delete --expunge --partialrun 500'
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        output, err = p.communicate()
        if p.returncode != 0:
            logger.error(f"ERROR: rspamd scan failed for account: {USERNAME}")
            logger.error(err)
        logger.info(output)

    def login():
        while True:
            try:
                server = IMAPClient(HOST)
                server.login(USERNAME, PASSWORD)
                server.select_folder(INPUT)
                server.idle()
                logger.info(f"Connection is now in IDLE mode for account: {USERNAME}")
                return server
            except Exception as e:
                logger.error(f"Failed to connect for account: {USERNAME} - trying again")
                logger.error(e)

    def logoff(server):
        server.idle_done()
        logger.info(f"IDLE mode done for account: {USERNAME}")
        server.logout()

    def pushing(server):
        count = 0
        while True:
            try:
                responses = server.idle_check(timeout=29)
                if responses:
                    logger.info(f"Response for account {USERNAME}: {responses}")
                    count = 0
                    scan_spam()
                else:
                    logger.info(f"No responses for account {USERNAME}")
                    count += 1
                if count > 25:
                    logger.info(f"No responses from Server for account {USERNAME} - Scan for Spam, then Restart")
                    scan_spam()
                    count = 0
                    raise Exception("No response")
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Push error for account: {USERNAME}")
                count = 0
                break

    # Start the IMAP IDLE process
    try:
        server = login()
        pushing(server)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Exception for account: {USERNAME}")
        logger.error(e)
    finally:
        logoff(server)

# Main execution
if __name__ == "__main__":
    # Retrieve and filter enabled accounts
    enabled_accounts = [acct for acct in datastore["antispambox"]["accounts"] if acct.get("enabled", "False").lower() == "true"]
    
    # Start a thread for each enabled account
    threads = []
    for account in enabled_accounts:
        t = Thread(target=handle_account, args=(account,))
        t.start()
        threads.append(t)

    # Wait for all threads to finish
    for t in threads:
        t.join()

    logger.info("Antispambox processing completed")

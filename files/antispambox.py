import json
import logging
from imapclient import IMAPClient
import sys
import subprocess
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger("Antispambox")
logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler('/var/log/antispambox.log', when="H", interval=24, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.addHandler(logging.StreamHandler())


class NoConnectionError(Exception):
    pass


def handle_account(account):
    host = account["server"]
    username = account["user"]
    password = account["password"]
    junk = account["junk_folder"]
    inbox = account["inbox_folder"]
    ham_train = account["ham_train_folder"]
    spam_train = account["spam_train_folder"]

    def scan_spam():
        logger.info(f"Scanning for SPAM with rspamd for account: {username}")

        cmd = f'/usr/local/bin/irsd --imaphost {host} --imapuser {username} --imappasswd {password} --spaminbox {junk} --imapinbox {inbox} --learnhambox {ham_train} --learnspambox {spam_train} --cachepath rspamd --delete --expunge --partialrun 500'
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            logger.error(f"ERROR: rspamd scan failed for account: {username}")
            logger.error(stderr.decode())
        else:
            logger.info(stdout.decode())

        logger.info(f"Training Rspamd with ham emails for account: {username}")
        train_emails(ham_train, 'learn_ham')

        logger.info(f"Training Rspamd with spam emails for account: {username}")
        train_emails(spam_train, 'learn_spam')

    def train_emails(folder_name, command):
        with IMAPClient(host, timeout=30) as client:
            client.login(username, password)
            client.select_folder(folder_name)
            messages = client.search()
            for msgid in messages:
                response = client.fetch(msgid, ['RFC822'])
                email_message = response[msgid][b'RFC822']
                process = subprocess.Popen(['rspamc', command], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)
                stdout, stderr = process.communicate(input=email_message)
                if process.returncode != 0:
                    logger.error(f"Error training message {msgid} with command {command}")
                    logger.error(stderr.decode())
                else:
                    logger.info(f"Trained message {msgid} with command {command}")
                    client.delete_messages(msgid)
                    client.expunge()

    def login():
        while True:
            try:
                with IMAPClient(host, timeout=30) as login_server:
                    login_server.login(username, password)
                    login_server.select_folder(inbox)
                    login_server.idle()
                    logger.info(f"Connection is now in IDLE mode for account: {username}")
                    return login_server
            except socket.timeout:
                logger.error(f"Timeout while connecting for account: {username}")
                time.sleep(5)  # Wartezeit vor erneutem Versuch
            except (socket.error, IMAPClient.Error) as e:
                logger.error(f"Connection error for account: {username}")
                logger.exception(e)
                raise NoConnectionError

    def logoff(logoff_server):
        logoff_server.idle_done()
        logger.info(f"IDLE mode done for account: {username}")
        logoff_server.logout()

    def pushing(push_server, push_username, login_func, scan_func):
        max_non_responses = 5
        max_count = 10
        count = 0

        while count <= max_count:
            try:
                responses = push_server.idle_check(timeout=600)
                if responses:
                    logger.info(f"Response for account {push_username}: {responses}")
                    scan_func()
                    count = 0
                else:
                    logger.info(f"No responses for account: {push_username}")
                    count += 1
                    if count > max_non_responses:
                        logger.info(f"Reconnecting for account {push_username} due to no response.")
                        push_server = login_func()  # Reconnect for the current account
                        count = 0
            except socket.timeout as ex:
                logger.error(f"Timeout while waiting for responses for account: {push_username}")
                logger.error(ex)
                count = 0  # Reset the counter on timeout
                break  # Break out of the loop on timeout
            except Exception as ex:
                logger.error(f"An error occurred for account: {push_username}")
                logger.error(ex)
                count = 0  # Reset the counter on other exceptions

        return push_server

    server = None
    try:
        server = login()
        server = pushing(server, username, login, scan_spam)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Exception for account: {username}")
        logger.error(e)
    finally:
        if server:
            logoff(server)


def process_account_group(accounts):
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(handle_account, account): account for account in accounts}
        for future in futures:
            try:
                future.result()
            except Exception as e:
                logger.error(f"Exception in processing account: {futures[future]} - {e}")


def process_accounts(accounts):
    group_size = 5
    for i in range(0, len(accounts), group_size):
        account_group = accounts[i:i + group_size]
        process_account_group(account_group)
        time.sleep(5)


if __name__ == "__main__":
    try:
        with open("/root/accounts/imap_accounts.json", 'r') as f:
            datastore = json.load(f)
    except (IndexError, json.JSONDecodeError) as e:
        logger.error("ERROR: Unable to read imap_accounts.json.")
        logger.error(e)
        sys.exit(1)

    enabled_accounts_main = [acct for acct in datastore["antispambox"]["accounts"] if
                             acct.get("enabled", "False").lower() == "true"]
    process_accounts(enabled_accounts_main)
    logger.info("Antispambox processing completed")
import json
import logging
from imapclient import IMAPClient
import subprocess
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


try:
    with open("/root/accounts/imap_accounts.json", 'r') as f:
        datastore = json.load(f)
except (IndexError, json.JSONDecodeError) as e:
    logger.error("ERROR: Unable to read imap_accounts.json.")
    logger.error(e)
    sys.exit(1)


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
        logger.info(stdout.decode())

    def login():
        while True:
            try:
                server = IMAPClient(host)
                server.login(username, password)
                server.select_folder(inbox)
                server.idle()
                logger.info(f"Connection is now in IDLE mode for account: {username}")
                return server
            except Exception as e:
                logger.error(f"Failed to connect for account: {username} - trying next account")
                logger.error(e)
                raise NoConnectionError

    def logoff(server):
        server.idle_done()
        logger.info(f"IDLE mode done for account: {username}")
        server.logout()

    def pushing(server):
        max_non_responses = 5
        count = 0
        max_count = 10  # Die Anzahl, nach der wir die Verbindung erneut herstellen

        while True:
            try:
                responses = server.idle_check(timeout=600)
                if responses:
                    logger.info(f"Response for account {username}: {responses}")
                    count = 0
                    scan_spam()
                else:
                    logger.info(f"No responses for account {username}")
                    count += 1
                    if count > max_non_responses:
                        count = 0
                        logger.info(f"Reconnecting for account {username} due to no response.")
                        server = login()  # Neue Verbindung herstellen
                    elif count > max_count:
                        break  # Wechsle zum nächsten Account
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Push error for account: {username}")
                count = 0
                break

    try:
        server = login()
        pushing(server)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Exception for account: {username}")
        logger.error(e)
    finally:
        logoff(server)


def process_accounts(accounts):
    for account in accounts:
        try:
            handle_account(account)
        except NoConnectionError:
            logger.info(f"Skipping account: {account['user']} due to connection error")
        except Exception as e:
            logger.error(f"Error processing account: {account['user']}")
            logger.error(e)


def main():
    enabled_accounts = [acct for acct in datastore["antispambox"]["accounts"] if
                        acct.get("enabled", "False").lower() == "true"]
    process_accounts(enabled_accounts)


if __name__ == "__main__":
    main()
    logger.info("Antispambox processing completed")

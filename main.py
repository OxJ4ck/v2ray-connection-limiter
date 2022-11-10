"""v2ray connection limiter"""
import os
import sqlite3
from time import sleep

import requests
import schedule

import config


def restart_x_ui():
    """restart x-ui to apply the changes"""
    os.popen("x-ui restart")


def get_users() -> list:
    """get all saved users in database

    Returns:
        list: remark and port of users
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("select remark,port from inbounds")
    return [dict(row) for row in cursor.fetchall()]


def disable_account(user_port: str) -> None:
    """restrict account access

    Args:
        user_port (str): port number of user
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(f"update inbounds set enable = 0 where port={user_port}")
    conn.commit()
    conn.close()


def send_to_telegram(user_remark: str) -> None:
    """send alert message to admin

    Args:
        user_remark (str): name of account
    """
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    params = {
        "chat_id": config.CHAT_ID,
        "text": user_remark + " has been blocked.",
    }
    requests.get(url, params=params, timeout=10)


def checker(user: dict) -> bool:
    """check user for active connection

    Args:
        user (dict): user to check

    Returns:
        bool: True if the number of connection is more than the maximum allowed, otherwise False
    """
    user_remark = user["remark"]
    user_port = user["port"]
    netstat_data = os.popen(
        "netstat -np 2>/dev/null | grep :"
        + str(user_port)
        + " | awk '{if($3!=0) print $5;}' | cut -d: -f1 | sort | uniq -c | sort -nr | head"
    ).read()
    netstat_data = str(netstat_data)
    connection_count = len(netstat_data.split("\n")) - 1
    if config.PRINT_OUTPUT:
        print(f"{user_remark:<12}{user_port:<12}{connection_count:<12}")
    if connection_count > config.MAX_ALLOWED_CONNECTIONS:
        disable_account(user_port=user_port)
        send_to_telegram(user_remark=user_remark)
        if config.PRINT_OUTPUT:
            print(f"inbound with port {user_port} blocked")
        return True
    return False


def run():
    """run the script"""
    need_restart = False
    users_list = get_users()
    if config.PRINT_OUTPUT:
        print(f"{'Remark':<12}{'Port':<12}{'Count':<12}")
    for user in users_list:
        if checker(user=user):
            need_restart = True

    if need_restart:
        restart_x_ui()


schedule.every(config.INTERVAL).seconds.do(run)

while True:
    schedule.run_pending()
    sleep(1)

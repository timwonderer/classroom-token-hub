"""Scratch probe file ONLY for verifying the code_scanning ruleset rule blocks merge.
This file is never meant to merge and will be deleted before this branch closes.
"""
import sqlite3


def lookup_user_by_name(connection: sqlite3.Connection, user_supplied_name: str):
    # Deliberately vulnerable: unsanitized input concatenated into a SQL query string.
    cursor = connection.cursor()
    query = "SELECT * FROM users WHERE name = '" + user_supplied_name + "'"
    cursor.execute(query)
    return cursor.fetchall()

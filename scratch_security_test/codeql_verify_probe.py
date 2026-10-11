"""Scratch probe file ONLY for verifying the code_scanning ruleset rule blocks merge.
This file is never meant to merge and will be deleted before this branch closes.
"""
import sqlite3

from flask import Blueprint, request

scratch_probe_bp = Blueprint("scratch_probe", __name__)


@scratch_probe_bp.route("/scratch-probe/lookup")
def lookup_user_by_name():
    connection = sqlite3.connect(":memory:")
    cursor = connection.cursor()
    # Deliberately vulnerable: request data concatenated straight into a SQL query string.
    name = request.args.get("name", "")
    query = "SELECT * FROM users WHERE name = '" + name + "'"
    cursor.execute(query)
    return str(cursor.fetchall())

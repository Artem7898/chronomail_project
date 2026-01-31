#!/usr/bin/env python
# wait_for_db.py

import sys
import time
import psycopg2
from django.db import connections
from django.db.utils import OperationalError

def wait_for_db():
    """Wait for database to be ready"""
    db_conn = connections['default']
    connected = False
    retries = 30
    
    for i in range(retries):
        try:
            db_conn.ensure_connection()
            connected = True
            break
        except (OperationalError, psycopg2.OperationalError) as e:
            if i < retries - 1:
                time.sleep(2)
                continue
            else:
                raise e
    
    return connected

if __name__ == '__main__':
    try:
        if wait_for_db():
            print("Database is ready!")
            sys.exit(0)
        else:
            print("Database connection failed")
            sys.exit(1)
    except Exception as e:
        print(f"Error waiting for database: {e}")
        sys.exit(1)

### config.py ###

import psycopg2

DATABASE_URI = 'postgres+psycopg2://<USERNAME>:<PASSWORD>@<IP_ADDRESS>:<PORT>/<DATABASE_NAME>'


CONNECTION = psycopg2.connect(
    host="HOST_NAME",
    database="db_name",
    user="USERNAME",
    password="PASSWORD"
    )
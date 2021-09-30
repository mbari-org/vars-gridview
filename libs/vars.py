# -*- coding: utf-8 -*-
"""
vars.py -- Tools to implement interactions with VARS
Copyright 2020  Monterey Bay Aquarium Research Institute
Distributed under MIT license. See license.txt for more information.

"""
import json
# --- Start --- Configure detailed HTTP logging
import logging
import os
from typing import Optional

import pymssql
import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG)
import http.client

httpclient_logger = logging.getLogger("http.client")


def httpclient_logging_patch(level=logging.DEBUG):
    """Enable HTTPConnection debug logging to the logging framework"""

    def httpclient_log(*args):
        httpclient_logger.log(level, " ".join(args))

    # mask the print() built-in in the http.client module to use
    # logging instead
    http.client.print = httpclient_log
    # enable debugging
    http.client.HTTPConnection.debuglevel = 1


httpclient_logging_patch()
# --- End --- Configure detailed HTTP logging


from gridview import MainWindow

SQL_CONNECTION: pymssql.Connection = None
BASE_QUERY: str = None


def auth_retry(fail_msg):
    """
    Decorator for REST calls with auth retry
    :param fail_msg: Message to show on fail
    :return: Wrapped function
    """

    def wrap_func(func):
        def retry_func(*args, retry=True, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if retry:
                    auth()
                    return retry_func(*args, retry=False, **kwargs)
                else:
                    print(fail_msg)
                    print(e)

        return retry_func

    return wrap_func


def auth():
    """
    Authenticate, generate new JWT access token and cache it
    :return: JWT access token
    """
    try:
        response = requests.post(
            get_source('anno_auth'),
            headers={
                'Authorization': 'APIKEY {}'.format(get_api_key())
            }
        )
        cache_token(response.content.decode())
        return response.json()['access_token']
    except Exception as e:
        print('Auth failed:')
        print(e)
        return None


def check_auth():
    """
    Check cached authentication token is valid, fetch new if not
    :return: Token str
    """
    token = get_token()
    if not token:
        token = auth()
    if not token:
        raise ValueError('Bad API key! Check it in config/api_key.txt')
    else:
        return token


def auth_header() -> dict:
    token = check_auth()

    return {
        'Authorization': 'BEARER {}'.format(token)
    }


def get_api_key():
    """
    Returns the API key for authorization from 'config/api_key.txt'
    :return: API key string
    """
    key = os.getenv('API_KEY')
    if key is None:
        load_dotenv()
    key = os.getenv('API_KEY')
    return key


def cache_token(token: str):
    """
    Caches a token to the 'cache/token.json'
    :param token: JWT access token JSON string
    :return: None
    """
    if not os.path.exists('cache'):
        os.makedirs('cache')
    with open('cache/token.json', 'w') as f:
        f.write(token)


def get_token():
    """
    Gets the JWT access token, if it exists
    :return: JWT access token string if exists, else None
    """
    if not os.path.exists('cache/token.json'):
        return None
    with open('cache/token.json', 'r') as f:
        access_token = json.loads(f.read())['access_token']
        return access_token


def get_source(key) -> str:
    return MainWindow.sources.value(key)


def pull_all_concepts(timeout=5):
    url = get_source('kb_concepts')
    r = requests.get(url, timeout=timeout)
    return r.json()


def pull_all_parts():
    url = get_source('kb_parts')
    r = requests.get(url)
    return ['', 'self'] + [el['name'] for el in r.json()]


def get_conn() -> Optional[pymssql.Connection]:
    global SQL_CONNECTION
    if SQL_CONNECTION is None:
        SQL_CONNECTION = pymssql.connect(server=get_source('server'),
                                         user=get_source('user'),
                                         password=get_source('password'),
                                         database=get_source('database'))
    return SQL_CONNECTION


def get_base_query() -> str:
    global BASE_QUERY
    if BASE_QUERY is None:
        with open('config/base_query.sql') as f:
            BASE_QUERY = f.read()
    return BASE_QUERY


def sql_query(query_text: str, **query_kwargs):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(query_text.format(**query_kwargs))

    return cursor.fetchall(), [i[0] for i in cursor.description]  # Data and column names


def make_query(filter_str: str) -> str:
    return get_base_query().format(filters=filter_str)


def get_all_users() -> list:
    url = get_source('accounts_users')
    res = requests.get(url)
    return res.json()


def get_concept_descendants(concept: str) -> list:
    def recursive_accumulate(tree):
        names = set()
        if 'children' not in tree:
            return names

        for child in tree['children']:
            names.add(child['name'])
            names = names.union(recursive_accumulate(child))

        return names

    url = get_source('kb_descendants')
    res = requests.get(url + '/' + concept)

    return recursive_accumulate(res.json())


@auth_retry('Box modification failed.')
def modify_box(box_json: dict, observation_uuid: str, association_uuid: str):
    request_data = {
        'observation_uuid': observation_uuid,
        'link_name': 'bounding box',
        'link_value': json.dumps(box_json),
        'mime_type': 'application/json'
    }

    response = requests.put(
        get_source('anno_associations') + '/' + association_uuid,
        data=request_data,
        headers=auth_header()
    )
    return response.json()


@auth_retry('Changing concept failed.')
def change_concept(observation_uuid: str, new_concept: str, observer: str):
    params = {
        'concept': new_concept,
        'observer': observer
    }

    response = requests.put(
        get_source('anno_annotations') + '/' + observation_uuid,
        params=params,
        headers=auth_header()
    )

    return response


@auth_retry('Changing part failed.')
def change_part(association_uuid: str, new_part: str):
    params = {
        'to_concept': new_part
    }

    response = requests.put(
        get_source('anno_associations') + '/' + association_uuid,
        params=params,
        headers=auth_header()
    )

    return response


@auth_retry('Box deletion failed.')
def delete_box(association_uuid: str):
    response = requests.delete(
        get_source('anno_associations') + '/' + association_uuid,
        headers=auth_header()
    )

    return response

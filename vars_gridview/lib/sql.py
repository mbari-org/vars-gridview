import sys
from typing import List, Optional, Tuple

import pymssql

from vars_gridview.lib.constants import BASE_QUERY_FILE, VIDEO_DATA_QUERY_FILE
from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.settings import SettingsManager

SQL_CONNECTION = None
BASE_QUERY = None
VIDEO_DATA_QUERY = None


class ORList:
    @staticmethod
    def typestr(value):
        if isinstance(value, str):
            return "%s"
        elif isinstance(value, int):
            return "%d"
        else:
            raise ValueError("Unsupported type: {}".format(type(value)))

    def __init__(self, key: str, values=None):
        self._key = key
        self._values = values or []

    def __iadd__(self, value):
        self._values.append(value)
        return self

    @property
    def form(self):
        return (
            "("
            + " OR ".join(
                [
                    "{} = {}".format(self._key, ORList.typestr(value))
                    for value in self._values
                ]
            )
            + ")"
        )

    @property
    def values(self):
        return self._values


class ConstraintSpec:
    def __init__(self, lists=None):
        self._lists = lists or []

    @property
    def form(self):
        if len(self._lists) == 0:
            return "1=1"  # Accept anything
        return " AND ".join(
            [list.form for list in self._lists]
        )  # AND together all forms

    @property
    def values(self):
        return [value for l in self._lists for value in l.values]  # Flatten all values

    @classmethod
    def from_dict(cls, d):
        return cls(lists=[ORList(key, values) for key, values in d.items()])


def get_base_query() -> str:
    """
    Read the base query.
    """
    global BASE_QUERY
    if not BASE_QUERY:
        with open(BASE_QUERY_FILE) as f:
            BASE_QUERY = f.read()

    return BASE_QUERY


def get_video_data_query() -> str:
    """
    Read the video data query.
    """
    global VIDEO_DATA_QUERY
    if not VIDEO_DATA_QUERY:
        with open(VIDEO_DATA_QUERY_FILE) as f:
            VIDEO_DATA_QUERY = f.read()
    
    return VIDEO_DATA_QUERY


def connect(server_url: str, user: str, password: str, database: str):
    """
    Initialize the connection to the SQL server.
    """
    global SQL_CONNECTION
    try:
        SQL_CONNECTION = pymssql.connect(
            server=server_url, user=user, password=password, database=database
        )
    except pymssql.DatabaseError as e:
        LOGGER.error(f"Failed to connect to SQL server: {e}")
        sys.exit(1)


def connect_from_settings():
    """
    Connect.
    """
    settings = SettingsManager.get_instance()

    connect(
        settings.sql_url.value,
        settings.sql_user.value,
        settings.sql_password.value,
        settings.sql_database.value,
    )


def run_query(query_str: str, values: Optional[tuple] = None) -> Tuple[list, list]:
    if not SQL_CONNECTION:
        raise Exception("No connection to SQL server")

    cursor = SQL_CONNECTION.cursor()
    cursor.execute(
        query_str,
        values if values is not None else tuple(),
    )

    return cursor.fetchall(), [
        i[0] for i in cursor.description
    ]  # Data and column names


def query(constraint_dict: dict) -> Tuple[list, list]:
    """
    Run the base query with the given constraints.
    """
    constraint_spec = ConstraintSpec.from_dict(constraint_dict)
    
    return run_query(
        get_base_query().format(filters=constraint_spec.form), 
        values=tuple(constraint_spec.values)
    )


def query_video_data(video_reference_uuids: List[str]) -> Tuple[list, list]:
    """
    Run the video data query with the given constraints.
    """
    formatted_uuids = "(" + ", ".join(["'{}'".format(uuid) for uuid in video_reference_uuids]) + ")"
    return run_query(get_video_data_query().format(video_reference_uuids=formatted_uuids))
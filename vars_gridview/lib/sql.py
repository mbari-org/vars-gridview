from typing import Tuple

import pymssql

from vars_gridview.lib.constants import BASE_QUERY_FILE
from vars_gridview.lib.log import LOGGER
from vars_gridview.lib.settings import SettingsManager

SQL_CONNECTION = None
BASE_QUERY = None


class ORList:
    @staticmethod
    def typestr(value):
        if isinstance(value, str):
            return f"'{value}'"
        elif isinstance(value, int):
            return f"{value}"
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
            [list_.form for list_ in self._lists]
        )  # AND together all forms

    @property
    def values(self):
        return [
            value for list_ in self._lists for value in list_.values
        ]  # Flatten all values

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


def connect(server_url: str, user: str, password: str, database: str):
    """
    Initialize the connection to the SQL server.
    """
    global SQL_CONNECTION
    SQL_CONNECTION = pymssql.connect(
        server=server_url,
        user=user,
        password=password,
        database=database,
        tds_version="7.0",
    )


def connect_from_settings():
    """
    Connect.
    """
    settings = SettingsManager.get_instance()

    url = settings.sql_url.value
    user = settings.sql_user.value
    password = settings.sql_password.value
    database = settings.sql_database.value

    connect(url, user, password, database)
    LOGGER.info(f"Connected to SQL server at {url}")


def query(constraint_dict: dict) -> Tuple[list, list]:
    if not SQL_CONNECTION:
        raise Exception("No connection to SQL server")

    constraint_spec = ConstraintSpec.from_dict(constraint_dict)

    cursor = SQL_CONNECTION.cursor()
    cursor.execute(
        get_base_query().format(filters=constraint_spec.form),
    )

    return cursor.fetchall(), [
        i[0] for i in cursor.description
    ]  # Data and column names

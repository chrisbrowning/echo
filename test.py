import pytest
import os
from app import app, sanitize, init_ddl, set_current_idx, set_country_data, analyze_results, register_result, reset_results
import sqlite3
from flask import session
import uuid

def test_sanitize():
    assert sanitize("A'B.C") == "abc"

country_data = []

@pytest.fixture()
def mockapp():
    mockapp = app
    mockapp.secret_key = "123"
    mockapp.config.from_pyfile('test.cfg')
    yield mockapp

@pytest.fixture
def client(mockapp):
    with mockapp.test_client() as client:
        with mockapp.app_context():
            init_ddl()
            init_test_country_data()
            set_country_data()
        yield client
    # tear down
    drop_results()

def drop_results():
    try:
        with sqlite3.connect(app.config["DB_FILE"]) as conn:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE results")
    except Exception as e:
        print(f"Unexpected exception: {e}")

def init_test_country_data():
    test_countries = [("1", "myfakecountry", "myfakeregion", "fakecapital"), ("2", "Shire", "Middle Earth", "Hobbiton")]
    try:
        with sqlite3.connect(app.config["DB_FILE"]) as conn:
            cursor = conn.cursor()
            cursor.executemany("INSERT OR IGNORE INTO countries (id, name, region, capitalCity) VALUES (?, ?, ?, ?)", test_countries)
            print(f"Inserted {cursor.rowcount} records into 'countries'.")
    except Exception as e:
        print(f"Unexpected exception: {e}")
    return country_data

def init_test_results():
    test_results = [
        ("1", "10.0.0.5", "myfakecountry", "myfakeregion", "fakecapital", 1),
        ("1", "10.0.0.5", "Shire", "Middle Earth", "Hobbiton", 1),
        ("2", "10.0.0.10", "myfakecountry", "myfakeregion", "fakecapital", 0),
        ("2", "10.0.0.10", "Shire", "Middle Earth", "Hobbiton", 1),
        ("3", "10.0.0.22", "myfakecountry", "myfakeregion", "fakecapital", 0),
        ]
    for tr in test_results:
        register_result(tr[0], tr[1], tr[2], tr[3], tr[4], tr[5])

def test_guess_fakecountry(client):
    with client.session_transaction() as session:
        # set a user id without going through the login route
        session["id"] = 1
    response = client.post("/guess", data={
        "user_input": "fakecapital"
    })
    assert response.status_code == 200
    assert b"fakecapital is correct" in response.data

def test_guess_shire(client):
    with client.session_transaction() as session:
        # set a user id without going through the login route
        session["id"] = 1
        session["cc"] = 1
    response = client.post("/guess", data={
        "user_input": "hobbiton"
    })
    assert response.status_code == 200
    assert b"Hobbiton is correct" in response.data

def test_analyze_results_user1(client):
    reset_results("1")
    init_test_results()
    user_results = analyze_results("1")
    assert user_results[0][0] == "Overall" # first value is region
    assert user_results[0][1] == 1.0 # pct_correct
    assert user_results[0][2] == 3 # outof
    assert user_results[0][3] == 1 # place

    assert user_results[1][0] == "Middle Earth" # first value is region
    assert user_results[1][1] == 1.0 # pct_correct
    assert user_results[1][2] == 2 # outof
    assert user_results[1][3] == 1 # place

    assert user_results[2][0] == "myfakeregion" # first value is region
    assert user_results[2][1] == 1.0 # pct_correct
    assert user_results[2][2] == 3 # outof
    assert user_results[2][3] == 1 # place

def test_analyze_results_user2(client):
    reset_results("1")
    init_test_results()
    user_results = analyze_results("2")
    assert user_results[0][0] == "Overall" # first value is region
    assert user_results[0][1] == 0.5 # pct_correct
    assert user_results[0][2] == 3 # outof
    assert user_results[0][3] == 2 # place

    assert user_results[1][0] == "Middle Earth" # first value is region
    assert user_results[1][1] == 1.0 # pct_correct
    assert user_results[1][2] == 2 # outof
    assert user_results[1][3] == 1 # place

    assert user_results[2][0] == "myfakeregion" # first value is region
    assert user_results[2][1] == 0.0 # pct_correct
    assert user_results[2][2] == 3 # outof
    assert user_results[2][3] == 2 # place  

def test_analyze_results_user3(client):
    reset_results("1")
    init_test_results()
    user_results = analyze_results("3")
    assert user_results[0][0] == "Overall" # first value is region
    assert user_results[0][1] == 0.0 # pct_correct
    assert user_results[0][2] == 3 # outof
    assert user_results[0][3] == 3 # place

    assert user_results[1][0] == "myfakeregion" # first value is region
    assert user_results[1][1] == 0.0 # pct_correct
    assert user_results[1][2] == 3 # outof
    assert user_results[1][3] == 2 # place
#!/usr/bin/env python3

from flask import Flask, request, session, jsonify
import random
import requests
import json
import uuid
import sqlite3
import re
import os
from waitress import serve

app = Flask(__name__)
app.secret_key = os.getenv('SESSION_SECRET')

country_data = []

@app.route("/")
def entry():
    new_session = False
    if 'id' not in session:
        session['id'] = str(uuid.uuid4())
        new_session = True
    current_idx = random.randrange(len(country_data))
    rand_country = country_data[current_idx][1]
    session['cc'] = current_idx
    if new_session:
        return '''
        <h3> Final Exam </h3>
        <h3> What is the capital of {0}?</h3>
        <form action="/guess" method="POST">
            <input name="user_input">
            <input type="submit" value="Submit!">
        </form>
        <h5> Note: Answers ignore spaces, punctuation, and case </h5>
        <h5> Data for this quiz provided by the World Bank</h5>
        '''.format(rand_country)
    else:
        pct_correct = analyze_results(session['id'])
        pct_correct_html = ""
        for item in pct_correct:
            pct_correct_html = pct_correct_html + f"<tr>\n <td>{item[0]}</td><td> {item[1]*100}% </td><td>   </td><td>{item[3]} out of {item[2]}</td></tr>\n"
        return '''
        <h3> Final Exam </h3>
        <break>
        <h4> Session Performance</h4>
        <table>
        <tr><td>Region</td><td> Correct </td><td>   </td><td>Rank</td></tr>
        {0}
        </table>
        <break>
        <h3> What is the capital of {1}?</h3>
        <form action="/guess" method="POST">
            <input name="user_input">
            <input type="submit" value="Submit!">
        </form>
        <h5> Note: Answers ignore spacing, punctuation, and case </h5>
        <form action="/reset" method="POST">
            <button type="submit">Reset Session History?</button>
        </form>
        <h5> Data for this quiz provided by the World Bank</h5>
        '''.format(pct_correct_html, rand_country)

@app.route("/guess", methods=["POST"])
def guess():
    current_idx = session.get('cc', 0)
    input_text = request.form.get("user_input", "")[0:20]
    answer = country_data[current_idx][3]
    credited = sanitize(input_text) == sanitize(answer)
    register_result(session['id'], request.remote_addr, country_data[current_idx][1], country_data[current_idx][2], answer, credited)
    if credited:
        return """
        {0} is correct
        <form action="/">
            <button type="submit">Continue?</button>
        </form>
        """.format(answer)
    else:
        return """
        Incorrect. The correct answer was {} and you said {}
        <form action="/">
            <button type="submit">Continue?</button>
        </form>
        """.format(answer, input_text)

def get_current_idx():
    return current_idx

def set_current_idx(idx):
    session['cc'] = idx

def register_result(session_id, ip, country, region, answer, credited):
    try:
        with sqlite3.connect(app.config["DB_FILE"]) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO results (session_id, ip, country, region, answer, credited) 
                VALUES (?,?,?,?,?,?)
            ''', (session_id, ip, country, region, answer, credited))   
            print(f"{ip} {session_id} {country} {credited}")

    except Exception as e:
        print(f"Unexpected exception: {e}")

def analyze_results(session_id):
    user_results = []
    try:
        with sqlite3.connect(app.config["DB_FILE"]) as conn:
            cursor = conn.cursor()

            # this is complicated but I can't think of something more elegant
            # for a given session_id, return the percent answered correctly and rank information per region (e.g. 1 out of 2)
            cursor.execute("""
            SELECT region, pct, outof, place
            FROM (
                SELECT session_id, priority, region, pct, COUNT(session_id) OVER (PARTITION BY region) as outof, rank() OVER win1 as place
                FROM (
                    SELECT session_id, 100 as priority, 'Overall' as region, SUM(credited) as total_credited, COUNT(*) as total_answered, CAST(SUM(credited) AS REAL) / COUNT(*) AS pct 
                    FROM results
                    GROUP BY session_id
                    UNION ALL
                    SELECT session_id, 0 as priority, region, SUM(credited) as total_credited, COUNT(*) as total_answered, CAST(SUM(credited) AS REAL) / COUNT(*) as pct
                    FROM results
                    GROUP BY session_id, region
                ) AS agg
                WINDOW win1 AS (PARTITION BY region ORDER BY pct DESC)
            ) as aggtwo
            WHERE session_id = ?
            ORDER BY priority desc
            """, (session_id,))
            user_results = cursor.fetchall()
    except Exception as e:
        print(f"Unexpected exception: {e}")
    return user_results

@app.route("/reset", methods=["POST"]) 
def reset():
    reset_results(session["id"])
    return """
    Results reset successfully.
    <form action="/">
        <button type="submit">Start Over?</button>
    </form>     
    """

def reset_results(session_id):
    try:
        with sqlite3.connect(app.config["DB_FILE"]) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            DELETE from results
            WHERE session_id = ?
            """, (session_id,))
    except Exception as e:
        print(f"Unexpected exception: {e}")    

# strip punctuation, whitespaces, and convert to lowercase
def sanitize(text):
    return re.sub(r'[^\w]', '', text).lower()

@app.route("/metrics")
def metrics():
    return jsonify(get_metrics_past_day())

def get_metrics_past_day():
    metrics = {}
    try:
        with sqlite3.connect(app.config["DB_FILE"]) as conn:
            cursor = conn.cursor()
            cursor.execute(
            """
            SELECT COUNT(DISTINCT session_id) as sessions, COUNT(*) as questions_answered
            FROM results
            WHERE timestamp > DATETIME('now', '-1 day')
            """)
            results = cursor.fetchone()
            metrics["sessions_24h"] = results[0]
            metrics["total_answered_24h"] = results[1]
            
    except Exception as e:
        print(f"Unexpected exception: {e}")      
    return metrics   

def init_ddl():
    try:
        with sqlite3.connect(app.config["DB_FILE"]) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS countries (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    region TEXT NOT NULL,
                    capitalCity TEXT NOT NULL
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS results (
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    session_id TEXT NOT NULL,
                    ip TEXT NOT NULL,
                    country TEXT NOT NULL,
                    region TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    credited INTEGER NOT NULL
                )
            ''')
    except Exception as e:
        print(f"Unexpected exception: {e}")


def init_country_data():
    try:
        with sqlite3.connect(app.config["DB_FILE"]) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM countries
            ''')
            countries = cursor.fetchall()
            # Check if we already have country data before pulling from the API
            if len(country_data) > 0:
                for country in countries:
                    country_data.append((country[0],country[1],country[2],country[3]))
            else:
                curr_page = 0
                pages = 1

                while curr_page <= pages:
                    next_url = f"https://api.worldbank.org/v2/country?format=json&page={curr_page + 1}"
                    r = requests.get(next_url)
                    payload = json.loads(r.text)
                    curr_page = payload[0]['page']
                    pages = payload[0]['pages']
                    content = payload[1]
                    for c in content:
                        if c['capitalCity'] is None or c['capitalCity'] == "":
                            continue
                        country_data.append((c['id'], c['name'], c['region']['value'], c['capitalCity']))

                cursor.executemany("INSERT OR IGNORE INTO countries (id, name, region, capitalCity) VALUES (?, ?, ?, ?)", country_data)
                print(f"Inserted {cursor.rowcount} records into 'countries'.")
    except Exception as e:
        print(f"Unexpected exception: {e}")

def set_country_data():
    try:
        with sqlite3.connect(app.config["DB_FILE"]) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM countries
            ''')
            countries = cursor.fetchall()
            for country in countries:
                country_data.append((country[0], country[1], country[2], country[3]))
    except Exception as e:
        print(f"Unexpected exception: {e}")    

# Uses the World Bank API to hydrate a DB of country data
# If a country already exists, it will be ignored during the insert
# In the unlikely event that a new country comes to exist in the world, it will be inserted :)

def run():
    app.config.from_pyfile('app.cfg')
    init_ddl()
    init_country_data()
    set_country_data()
    serve(app, host="0.0.0.0", port=8080)
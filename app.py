#!/usr/bin/env python3

from flask import Flask, request, session
import random
import requests
import json

app = Flask(__name__)
app.secret_key = "1239075612312312"

curr_page = 0
pages = 1
country_data = []

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
        country_data.append(c)
    
current_idx = 0

@app.route("/")
def main():
    current_idx = random.randrange(len(country_data))
    rand_country = country_data[current_idx]['name']
    session['cc'] = current_idx
    return '''
    <h3> What is the capital of {0}?</h3>
     <form action="/guess" method="POST">
         <input name="user_input">
         <input type="submit" value="Submit!">
     </form>
     '''.format(rand_country)

@app.route("/guess", methods=["POST"])
def guess():
    reponse = ""
    current_idx = session.get('cc', 0)
    input_text = request.form.get("user_input", "")
    answer = country_data[current_idx]['capitalCity']
    if input_text == answer:
        return """
        Correct!
        <form action="/">
            <button type="submit">Try again??</button>
        </form>
        """
    else:
        return """
        Incorrect! The correct answer was {0}
        <form action="/">
            <button type="submit">Try again??</button>
        </form>
        """.format(answer)

def get_current_idx():
    return current_idx
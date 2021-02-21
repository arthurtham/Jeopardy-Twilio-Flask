from flask import Flask, request
from flask_cors import CORS

from urllib import request as requests
from urllib.parse import urlencode

import json
import ast

from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

from dotenv import load_dotenv

load_dotenv()

import os
import string
import random
import shelve
import json

# Flask setup
app = Flask(__name__)
CORS(app)

# Twilio setup

***REMOVED***
***REMOVED***
ACCOUNT_SID = os.environ.get("ACCOUNT_SID")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN")
twilio_number = os.environ.get("twilio_number")

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Python shelf setup
game_state_location = "./game_state"
player_state_location = "./player_state"

# Python questions setup
questions_location = "./questions.json"


# Auxillary Twilio functions
def send_message(to_number, msg):
    message = client.messages.create(
        to=to_number,
        from_=twilio_number,
        body=msg)

    return message.sid


# Game functions
def generate_question_from_json():
    data = ""
    with open(questions_location) as questions_file:
        data = json.load(questions_file)

    return data["questions"][random.randint(0, len(data) - 1)]


def create_game():
    with shelve.open(game_state_location, writeback=True) as game_state_database:
        while True:
            room_code = ""
            for _i in range(4):
                room_code += random.choice(string.ascii_letters)
            room_code = room_code.lower()
            if room_code not in game_state_database:
                question = generate_question_from_json()
                game_state_database[room_code] = {
                    "game_started": False,
                    "game_resolved": False,
                    "game_wagered": False,
                    "category": question["category"],
                    "question": question["question"],
                    "answer_choices": question["choices"],
                    "correct_answer": question["answer"]
                }
                print(room_code)
                return room_code


def get_question(room_code):
    with shelve.open(game_state_location) as game_state_database:
        entry = game_state_database[room_code]
        return entry["question"], entry["answer_choices"], entry["correct_answer"]


def lock_wagers(room_code):
    with shelve.open(game_state_location, writeback=True) as game_state_database:
        entry = game_state_database[room_code]
        print(entry)
        if not entry["game_wagered"]:
            entry["game_wagered"] = True
            result = [entry["question"], entry["answer_choices"], entry["correct_answer"], entry["category"]]
        else:
            return "wagering already closed"

    # Ask the question
    with shelve.open(player_state_location, writeback=True) as player_state_database:
        for _item in player_state_database:
            player, entry = _item, player_state_database[_item]
            if entry["game_id"] == room_code:
                if entry["wager"] == -1:
                    send_message(player, "You didn't wager anything and cannot participate in Final Jeopardy.")
                else:
                    send_message(player, f"Here's your FINAL JEOPARDY answer: " +
                             f"{result[0]} \n\nA: {result[1][0]}\n" +
                             f"B: {result[1][1]}\nC: {result[1][2]}\n\n" +
                             f"Answer by typing 'answer [A, B, C]'.")
    return "wagers closed"

def start_game(room_code):
    with shelve.open(game_state_location, writeback=True) as game_state_database:
        entry = game_state_database[room_code]
        print(entry)
        if not entry["game_started"]:
            entry["game_started"] = True
            # print(entry)
            # print(game_state_database[room_code])
            # TODO: initiate sequence
            # game_state_database.sync()
            result = [entry["question"], entry["answer_choices"], entry["correct_answer"], entry["category"]]
        else:
            # print("LOL")
            result = ["game_already_started"]

    if result[0] != "game_already_started":
        with shelve.open(player_state_location, writeback=True) as player_state_database:
            for _item in player_state_database:
                player, entry = _item, player_state_database[_item]
                if entry["game_id"] == room_code:
                    send_message(player, f"The category is '{result[3]}'. How much would you like to wager from your {entry['bank']} points?\n\n(Respond with 'wager [number]')")
        result = f"{result[0]};{result[1][0]};{result[1][1]};{result[1][2]};{result[2]};{result[3]}"
    else:
        result = result[0]
    print(result)
    return result


def resolve_game(room_code):
    # TODO: assign scores
    questions_entry = get_question(room_code)
    correct = 0
    incorrect = 0
    answer_a = 0
    answer_b = 0
    answer_c = 0
    answer_entry = "null"
    if questions_entry[2] == "a":
        answer_entry = questions_entry[1][0]
    elif questions_entry[2] == "b":
        answer_entry = questions_entry[1][1]
    elif questions_entry[2] == "c":
        answer_entry = questions_entry[1][2]

    # TODO: get player answers
    with shelve.open(player_state_location, writeback=True) as player_state_database:
        for _item in player_state_database:
            player, entry = _item, player_state_database[_item]
            if entry["game_id"] == room_code:
                if int(entry["wager"]) == -1:
                    #send_message(player, "You didn't wager anything!")
                    pass
                elif entry["answer"] == questions_entry[2]:
                    # TODO: correct answer
                    player_state_database[player]["bank"] += int(entry["wager"])
                    send_message(player, f"You are correct! Congrats! You win {entry['wager']} and now have {player_state_database[player]['bank']} points")
                    correct += 1
                elif entry["answer"] == 0:
                    player_state_database[player]["bank"] -= int(entry["wager"])
                    send_message(player, f"You didn't answer and lost {entry['wager']}. You now have {player_state_database[player]['bank']} points.")
                else:
                    # TODO: incorrect answer
                    player_state_database[player]["bank"] -= int(entry["wager"])
                    send_message(player, f"You are incorrect. Sorry. You lost {entry['wager']} and now have {player_state_database[player]['bank']} points.")
                    incorrect += 1

                if entry["answer"] == "a":
                    answer_a += 1
                elif entry["answer"] == "b":
                    answer_b += 1
                elif entry["answer"] == "c":
                    answer_c += 1

            player_state_database[player]["answer"] = 0
            # TODO: store the data to return to unity for results

    with shelve.open(game_state_location, writeback=True) as game_state_database:
        game_state_database[room_code]["game_resolved"]: True
        del game_state_database[room_code]

    # Return: Unity will show how many people got it right
    # Should we construct an object?
    return f"{correct},{incorrect},{answer_a},{answer_b},{answer_c},{answer_entry}"

    # return "game resolved"


def is_game_exists(room_code):
    with shelve.open(game_state_location) as game_state_database:
        return room_code in game_state_database


def is_game_active(room_code):
    if not is_game_exists(room_code):
        return False
    with shelve.open(game_state_location) as game_state_database:
        return game_state_database[room_code]["game_resolved"] == False


def get_player_count_by_room_code(room_code):
    result = 0
    with shelve.open(player_state_location) as player_state_database:
        for player, entry in player_state_database:
            if entry["game_id"] == room_code:
                result += 1
    return result


# Player functions
def play(player_number, game_id):
    with shelve.open(player_state_location, writeback=True) as player_state_database:
        if player_number in player_state_database and player_state_database[player_number]['game_id'] == game_id:
            send_message(player_number,
                         f"You've already joined a game: {player_state_database[player_number]['game_id']}. Please wait for the game to start.")
            return -1
        else:
            # TODO: does the game exist
            if len(game_id) != 4 or not is_game_exists(game_id):
                send_message(player_number, f"The game {game_id} doesn't exist. Please try again.")
                return -1
            if player_number not in player_state_database:
                player_state_database[player_number] = {
                    "game_id": game_id,
                    "answer": 0,
                    "wager": -1,
                    "bank": 1000
                }
            else:
                # Don't waste the bank
                player_state_database[player_number]["game_id"] = game_id;
                player_state_database[player_number]["wager"] = -1;
                player_state_database[player_number]["answer"] = 0;

            send_message(player_number,
                         f"Joined game {player_state_database[player_number]['game_id']}! Please wait for the game to start...")
            return 1


def reset(player_number):
    with shelve.open(player_state_location, writeback=True) as player_state_database:
        if player_number in player_state_database:
            player_state_database[player_number]["game_id"] = ""
            send_message(player_number, "Game ID reset!")
        else:
            send_message(player_number, "The player hasn't played this game before!")


def wager(player_number, amount_wagered):
    # TODO: tell the player to wager money
    with shelve.open(player_state_location, writeback=True) as player_state_database:
        if player_number in player_state_database:
            if player_state_database[player_number]["wager"] == -1:
                amount_wagered = int(amount_wagered)
                if amount_wagered > max(player_state_database[player_number]["bank"], 1000):
                    send_message(player_number, "You can't wager more than what you have in your bank!")
                elif amount_wagered < 0:
                    send_message(player_number, "You can't wager a negative amount of points!")
                else:
                    player_state_database[player_number]["wager"] = amount_wagered
                    send_message(player_number, "You made your wager. Waiting for other players...")
            else:
                send_message(player_number, "You already wagered!")
        else:
            send_message(player_number, "Try joining a game first!")
    return "wager function"


def answer(player_number, answer):
    with shelve.open(player_state_location, writeback=True) as player_state_database:
        player_entry = player_state_database[player_number]
        game_id = player_entry["game_id"]
        if is_game_active(game_id):
            if player_entry["wager"] == -1:
                send_message(player_number, "You didn't wager anything and cannot participate in Final Jeopardy.")
            elif player_entry["answer"] not in ["a", "b", "c", 0]:
                send_message(player_number, "You already answered this question!")
            else:
                # TODO: what is the convention for answering?
                player_answer = answer.lower().strip()[0]
                if player_answer == 1:
                    player_answer = "a"
                elif player_answer == 2:
                    player_answer = "b"
                elif player_answer == 3:
                    player_answer = "c"

                if player_answer not in ["a", "b", "c"]:
                    send_message(player_number, "That's not a valid answer input!")
                    return

                # Submit answer
                player_entry["answer"] = player_answer
                send_message(player_number, "Answer submitted. Waiting on other contestants...")
        else:
            send_message(player_number, f"Time is already up or the game doesn't exist for game id {game_id}!")


def money(player_number):
    # TODO: tell the player how much money they have in the bank
    with shelve.open(player_state_location, writeback=True) as player_state_database:
        if player_number in player_state_database:
            send_message(player_number, f"You have {player_state_database[player_number]['wager']} points!")

@app.route("/unity", methods=["GET", "POST"])
def unity_handler():
    print(request.values)

    command = request.values.get("command")
    print(command)
    result = ""

    #try:
    if command == "start":
        result = str(start_game(request.values.get("room_code")))
    elif command == "get_count":
        pass
    elif command == "create":
        result = create_game()
    elif command == "closewager":
        result = lock_wagers(request.values.get("room_code"))
    elif command == "resolve":
        result = resolve_game(request.values.get("room_code"))
    else:
        result = "invalid"

    return result
    # except Exception as e:
    #     print(e.__repr__())
    #     return "invalid"


@app.route("/twilio", methods=["POST"])
def request_handler():
    print(request.values)

    incoming_number = str(request.values.get("From", ""))
    incoming_msg = request.values.get('Body', '').lower()

    # The message must be in an order of:
    # [command] [payload (Game code, or answer)]
    incoming_msg = incoming_msg.split()
    print(incoming_msg)

    command = incoming_msg[0]
    payload = incoming_msg

    if command == "play":
        if len(payload) != 2:
            send_message(incoming_number, "Please type 'play {room_code}'")
        else:
            play(incoming_number, payload[1])
    elif command == "answer":
        if len(payload) != 2:
            send_message(incoming_number, "Please type 'answer {A,B,C,D}'")
        else:
            answer(incoming_number, payload[1])
    elif command == "wager":
        if len(payload) != 2:
            send_message(incoming_number, "Please type 'wager {number}'")
        else:
            wager(incoming_number, payload[1])
    elif command == "bank":
        money(incoming_number)
    else:
        send_message(incoming_number, "Uh oh! This command doesn't do anything.")
    # send_message(incoming_number, str(incoming_msg))

    return ""


if __name__ == "__main__":
    # from waitress import serve
    # serve(app, host='0.0.0.0', port=5000)
    # print(create_game())
    app.run(host="localhost", port=5000)

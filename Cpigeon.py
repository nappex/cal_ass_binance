#!/usr/bin/env python3
import csv
import hashlib
import hmac
import json
import os
from datetime import date
from time import time
from urllib.parse import urlencode, urljoin

import requests
from requests.exceptions import HTTPError

# Any stable coin - All coins will be calculate to this currency
FINAL_CURRENCY = "USDT"
API_KEY = "your API_KEY"
SECRET_KEY = "your SECRET_KEY"
BASE_URL = "https://api.binance.com"
HEADERS = {
    'X-MBX-APIKEY': API_KEY
}


def telegram_bot_sendtext(bot_message):
    """
    Send your own message to your telegram bot.
    """
    bot_token = 'your token'
    bot_chatID = 'your chatID'
    send_text = 'https://api.telegram.org/bot' + bot_token + \
        '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message
    try:
        r = requests.get(send_text)
        r.raise_for_status()
    except HTTPError as http_err:
        print(f"HTTP error occured: {http_err}")
    except Exception as err:
        print(f"Error occured: {err}")


def create_send_msg(fCurrency_balance, aux_history, to_day):
    la_fi_delta = round(aux_history[-1] - aux_history[0], 2)
    day_delta = round(aux_history[-1] - aux_history[-2], 2)
    # Customize your message
    my_msg = f"{to_day} daily report:\n" +\
        f"Current balance: {fCurrency_balance} '{FINAL_CURRENCY}'\n" + \
        f"Yesterday diff: {day_delta} '{FINAL_CURRENCY}'\n" + \
        f"All time diff: {la_fi_delta} '{FINAL_CURRENCY}'"
    telegram_bot_sendtext(my_msg)


def get_account_balances():
    """
    Get informations about balances on your binance account.
    Informations are about all coins which are listed on binance.
    """
    api_acc_path = "/api/v3/account"
    timestamp = int(time() * 1000)
    params = {
        "recvWindow": 5000,
        "timestamp": timestamp
    }
    query_string = urlencode(params)
    params['signature'] = hmac.new(SECRET_KEY.encode(
        'utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

    url = urljoin(BASE_URL, api_acc_path)

    try:
        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
    except HTTPError as http_err:
        print(f"HTTP error occured: {http_err}")
    except Exception as err:
        print(f"Error occured: {err}")

    return r.json()["balances"]


def get_spec_assets(balances, assets):
    """
    Select only coins which user wants to calculate for final asset.
    """
    your_balances = {}
    choosed_assets = [a.upper() for a in assets]
    for balance in balances:
        asset = balance["asset"]
        if asset in choosed_assets:
            your_balances[asset] = float(balance.get(
                "free", 0)) + float(balance.get("locked", 0))
    if not your_balances:
        print("Your codes of coins did not found.")

    return your_balances


def get_crypto_price(currencyPair):
    """
    Calculate price for choosed crypto coin.
    currencyPair is string joined from
    code of coin you want to find out value
    of stable coin and code of stable coin.
    Example: "ETHUSDT", "BTCUSDC", etc.
    """
    api_price_path = '/api/v3/ticker/price'
    params = {
        'symbol': currencyPair
    }

    url = urljoin(BASE_URL, api_price_path)
    try:
        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        price = round(float(r.json()["price"]), 2)
        return price
    except HTTPError as http_err:
        print(f"HTTP error occured: {http_err}")
    except Exception as err:
        print(f"Error occured: {err}")


def get_finalCurrency_balance(selected_balances):
    """
    Sum your choosed coins in value of stable coin you
    choosed(final_currency).
    Also add your balance of your stable coin.
    """
    usdt_sum = 0
    for asset, value in selected_balances.items():
        if asset != FINAL_CURRENCY:
            currency_pair = (asset + FINAL_CURRENCY).upper()
            crypto_price = get_crypto_price(currency_pair)
            usdt_sum += value * crypto_price
        else:
            usdt_sum += value

    return round(usdt_sum, 2)


def get_json_prices(json_path):
    """
    Loading saved the first price all time and last four price for
    next calculations or analyze.
    """
    if not os.path.exists(json_path):
        saved_prices = []
        with open(json_path, mode="w")as json_file:
            json.dump(saved_prices, json_file)
        return saved_prices
    else:
        with open(json_path, mode="r")as json_file:
            data = json.load(json_file)
            return data


def save_json_prices(json_path, prices):
    with open(json_path, mode="w")as file:
        json.dump(prices, file)


def balance_history_csv(csv_path, json_file, selected_balances, to_day, usdt_balance):
    """
    Create .csv file.
    All prices history during running script is saved to file.
    """
    header = ["Date"]
    csv_row = [to_day]
    for asset in selected_balances:
        if asset != FINAL_CURRENCY:
            currency_pair = asset + FINAL_CURRENCY
            header.extend([asset, asset + FINAL_CURRENCY])
            csv_row.extend([selected_balances[asset],
                            get_crypto_price(currency_pair)])
        else:
            header.append(asset)
            csv_row.append(selected_balances[asset])
    header.append(f"Account balance '{FINAL_CURRENCY}'")
    csv_row.append(usdt_balance)
    if not os.path.exists(csv_path):
        with open(csv_path, mode="w")as csvFile:
            csvFile_writer = csv.writer(csvFile)
            csvFile_writer.writerows([header, csv_row])
    else:
        with open(csv_path, mode="r")as csvFile:
            csvFile_reader = csv.reader(csvFile)
            file_header = list(csvFile_reader)[0]

        if file_header != header:
            os.remove(json_file)
            with open(csv_path, mode="w")as csvFile:
                csvFile_writer = csv.writer(csvFile)
                csvFile_writer.writerows([header, csv_row])
        else:
            with open(csv_path, mode="a")as csvFile:
                csvFile_writer = csv.writer(csvFile)
                csvFile_writer.writerow(csv_row)


def abs_path(path, file):
    rel_path = os.path.join(path, file)
    return os.path.abspath(rel_path)


def main():
    # set name of json file
    json_file = "temp_prices.json"
    # set name of csv file
    csv_file = "prices_allhist.csv"

    script_path = os.path.dirname(__file__)
    # set coins - to find out their value in stable coin
    assets = ["BTC", "ETH"]
    assets.append(FINAL_CURRENCY)

    acc_balances = get_account_balances()
    selected_balances = get_spec_assets(acc_balances, assets)
    fCurrency_balance = get_finalCurrency_balance(selected_balances)
    to_day = date.today().strftime("%d.%m.%Y")
    balance_history_csv(abs_path(script_path, csv_file), abs_path(script_path, json_file),
                        selected_balances, to_day, fCurrency_balance)

    aux_history = get_json_prices(abs_path(script_path, json_file))
    aux_history.append(fCurrency_balance)
    if len(aux_history) > 4:
        create_send_msg(fCurrency_balance, aux_history, to_day)
        del aux_history[1]

    save_json_prices(abs_path(script_path, json_file), aux_history)


if __name__ == "__main__":
    main()

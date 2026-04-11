from flask import Flask, request, jsonify
import requests
import os
import math

app = Flask(__name__)

YANDEX_GEOCODER_KEY = os.environ.get("YANDEX_GEOCODER_KEY", "")

# Координаты магазина
SHOP_LAT = 42.316541
SHOP_LON = 69.634382


def geocode_address(address):
    url = "https://geocode-maps.yandex.ru/1.x/"
    params = {
        "apikey": YANDEX_GEOCODER_KEY,
        "geocode": f"Шымкент, {address}",
        "format": "json",
        "results": 1,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        pos = (
            data["response"]["GeoObjectCollection"]
            ["featureMember"][0]["GeoObject"]
            ["Point"]["pos"]
        )
        lon, lat = map(float, pos.split())
        return lat, lon
    except Exception:
        return None, None


def calculate_distance_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def calculate_delivery_price(distance_km):
    if distance_km <= 3:
        price = 700
    else:
        extra_km = distance_km - 3
        price = 700 + (extra_km * 150)
    return min(round(price), 3000)


@app.route("/calculate-delivery", methods=["POST"])
def calculate_delivery():
    data = request.get_json(force=True, silent=True) or {}
    address = data.get("address", "").strip()

    if not address or address == "test":
        return jsonify({
            "version": "v2",
            "content": {
                "messages": [
                    {"type": "text", "text": "Пожалуйста, введите ваш адрес доставки."}
                ]
            },
            "actions": [],
            "quick_replies": []
        })

    client_lat, client_lon = geocode_address(address)
    if client_lat is None:
        return jsonify({
            "version": "v2",
            "content": {
                "messages": [
                    {"type": "text", "text": "Адрес не найден. Уточните адрес и попробуйте снова."}
                ]
            },
            "actions": [],
            "quick_replies": []
        })

    distance_km = calculate_distance_km(SHOP_LAT, SHOP_LON, client_lat, client_lon)
    price = calculate_delivery_price(distance_km)

    message = f"Доставка по адресу: {address}\nРасстояние: {distance_km:.1f} км\nСтоимость доставки: {price} тенге"

    return jsonify({
        "version": "v2",
        "content": {
            "messages": [
                {"type": "text", "text": message}
            ]
        },
        "actions": [],
        "quick_replies": []
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

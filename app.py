from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

YANDEX_GEOCODER_KEY = os.environ.get("YANDEX_GEOCODER_KEY", "")
YANDEX_DELIVERY_TOKEN = os.environ.get("YANDEX_DELIVERY_TOKEN", "")
SHOP_LONGITUDE = float(os.environ.get("SHOP_LONGITUDE", "69.5765"))
SHOP_LATITUDE = float(os.environ.get("SHOP_LATITUDE", "42.3417"))
SHOP_NAME = os.environ.get("SHOP_NAME", "Наш магазин")


def geocode_address(address: str):
    url = "https://geocode-maps.yandex.ru/1.x/"
    params = {
        "apikey": YANDEX_GEOCODER_KEY,
        "geocode": address,
        "format": "json",
        "results": 1,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    try:
        pos = (
            data["response"]["GeoObjectCollection"]
            ["featureMember"][0]["GeoObject"]
            ["Point"]["pos"]
        )
        lon, lat = map(float, pos.split())
        return lon, lat
    except (KeyError, IndexError, ValueError):
        return None, None


def get_delivery_price(client_lon: float, client_lat: float):
    url = "https://b2b.taxi.yandex.net/b2b/cargo/integration/v2/check-price"
    headers = {
        "Authorization": f"Bearer {YANDEX_DELIVERY_TOKEN}",
        "Content-Type": "application/json",
        "Accept-Language": "ru",
    }
    body = {
        "items": [
            {
                "size": {"length": 0.3, "width": 0.2, "height": 0.1},
                "weight": 1.0,
                "quantity": 1,
            }
        ],
        "route_points": [
            {"coordinates": [SHOP_LONGITUDE, SHOP_LATITUDE], "type": "source"},
            {"coordinates": [client_lon, client_lat], "type": "destination"},
        ],
        "fullname": SHOP_NAME,
    }
    resp = requests.post(url, json=body, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    try:
        return data["price"], data.get("currency", "RUB")
    except KeyError:
        return None, None


@app.route("/calculate-delivery", methods=["POST"])
def calculate_delivery():
    data = request.get_json(force=True, silent=True) or {}
    address = data.get("address", "").strip()

    if not address:
        return jsonify({
            "price": "не определена",
            "message": "❌ Адрес не указан. Пожалуйста, введите адрес доставки."
        })

    lon, lat = geocode_address(address)
    if lon is None:
        return jsonify({
            "price": "не определена",
            "message": "❌ Не удалось определить адрес. Уточните адрес и попробуйте снова."
        })

    price, currency = get_delivery_price(lon, lat)
    if price is None:
        return jsonify({
            "price": "не определена",
            "message": "❌ Не удалось рассчитать стоимость доставки. Попробуйте позже."
        })

    message = f"🚚 Стоимость доставки по адресу {address}: {price} {currency}"
    return jsonify({"price": f"{price} {currency}", "message": message})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

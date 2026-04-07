from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# ─── Настройки (заменить на свои) ───────────────────────────────────────────
YANDEX_GEOCODER_KEY = os.environ.get("YANDEX_GEOCODER_KEY", "ВАШ_КЛЮЧ_ГЕОКОДЕРА")
YANDEX_DELIVERY_TOKEN = os.environ.get("YANDEX_DELIVERY_TOKEN", "ВАШ_ТОКЕН_ДОСТАВКИ")
MANYCHAT_API_KEY = os.environ.get("MANYCHAT_API_KEY", "ВАШ_КЛЮЧ_MANYCHAT")

# Координаты вашего магазина [долгота, широта]
SHOP_LONGITUDE = float(os.environ.get("SHOP_LONGITUDE", "69.5765"))
SHOP_LATITUDE = float(os.environ.get("SHOP_LATITUDE", "42.3417"))
SHOP_NAME = os.environ.get("SHOP_NAME", "Наш магазин")
# ────────────────────────────────────────────────────────────────────────────


def geocode_address(address: str):
    """Получить координаты по адресу через Яндекс Геокодер"""
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
    """Получить стоимость доставки через Яндекс Доставку"""
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
            {
                "coordinates": [SHOP_LONGITUDE, SHOP_LATITUDE],
                "type": "source",
            },
            {
                "coordinates": [client_lon, client_lat],
                "type": "destination",
            },
        ],
        "fullname": SHOP_NAME,
    }
    resp = requests.post(url, json=body, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    try:
        price = data["price"]
        currency = data.get("currency", "RUB")
        return price, currency
    except KeyError:
        return None, None


def send_manychat_message(subscriber_id: str, text: str):
    """Отправить сообщение пользователю через ManyChat"""
    url = "https://api.manychat.com/fb/sending/sendContent"
    headers = {
        "Authorization": f"Bearer {MANYCHAT_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "subscriber_id": subscriber_id,
        "data": {
            "version": "v2",
            "content": {
                "messages": [{"type": "text", "text": text}]
            },
        },
    }
    resp = requests.post(url, json=body, headers=headers, timeout=10)
    return resp.status_code == 200


@app.route("/calculate-delivery", methods=["POST"])
def calculate_delivery():
    """
    Основной endpoint.
    ManyChat отправляет сюда:
      { "address": "...", "subscriber_id": "..." }
    """
    data = request.get_json(force=True, silent=True) or {}
    address = data.get("address", "").strip()
    subscriber_id = str(data.get("subscriber_id", "")).strip()

    if not address or not subscriber_id:
        return jsonify({"error": "Нужны address и subscriber_id"}), 400

    # 1. Геокодируем адрес
    lon, lat = geocode_address(address)
    if lon is None:
        send_manychat_message(
            subscriber_id,
            "❌ Не удалось определить ваш адрес. Пожалуйста, уточните адрес и попробуйте снова."
        )
        return jsonify({"error": "Адрес не найден"}), 422

    # 2. Рассчитываем стоимость
    price, currency = get_delivery_price(lon, lat)
    if price is None:
        send_manychat_message(
            subscriber_id,
            "❌ Не удалось рассчитать стоимость доставки. Попробуйте позже."
        )
        return jsonify({"error": "Ошибка Яндекс Доставки"}), 502

    # 3. Отправляем результат клиенту
    message = (
        f"🚚 Стоимость доставки по адресу:\n"
        f"📍 {address}\n\n"
        f"💰 {price} {currency}"
    )
    send_manychat_message(subscriber_id, message)

    return jsonify({"price": price, "currency": currency, "address": address})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

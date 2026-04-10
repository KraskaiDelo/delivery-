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
    """Получаем координаты адреса клиента"""
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
    """Считаем расстояние между двумя точками в км (формула Haversine)"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def calculate_delivery_price(distance_km):
    """
    Тариф доставки по Шымкенту:
    - До 3 км: 700₸
    - Свыше 3 км: 700₸ + 150₸ за каждый км сверх 3
    - Максимум: 3000₸
    """
    if distance_km <= 3:
        price = 700
    else:
        extra_km = distance_km - 3
        price = 700 + (extra_km * 150)

    price = min(round(price), 3000)
    return price


@app.route("/calculate-delivery", methods=["POST"])
def calculate_delivery():
    """
    ManyChat External Request отправляет:
      { "address": "ул. Абая 10" }
    Возвращает:
      { "price": "700 ₸", "distance": "2.3 км", "message": "..." }
    """
    data = request.get_json(force=True, silent=True) or {}
    address = data.get("address", "").strip()

    if not address:
        return jsonify({
            "price": "не определена",
            "distance": "неизвестно",
            "message": "❌ Адрес не указан. Пожалуйста, введите адрес доставки."
        })

    # Геокодируем адрес клиента
    client_lat, client_lon = geocode_address(address)
    if client_lat is None:
        return jsonify({
            "price": "не определена",
            "distance": "неизвестно",
            "message": "❌ Адрес не найден. Уточните адрес и попробуйте снова."
        })

    # Считаем расстояние
    distance_km = calculate_distance_km(SHOP_LAT, SHOP_LON, client_lat, client_lon)

    # Считаем цену
    price = calculate_delivery_price(distance_km)

    message = (
        f"🚚 Доставка по адресу: {address}\n"
        f"📍 Расстояние: {distance_km:.1f} км\n"
        f"💰 Стоимость доставки: {price} ₸"
    )

    return jsonify({
        "price": f"{price} ₸",
        "distance": f"{distance_km:.1f} км",
        "message": message
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

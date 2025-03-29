import requests

def get_coordinates_opencage(place):
    api_key = "0cd277781a214ffc99f6fac5f756f680"  # Reemplázala con tu clave de OpenCage
    url = f"https://api.opencagedata.com/geocode/v1/json?q={place}&key={api_key}"

    response = requests.get(url)
    data = response.json()

    if data["results"]:
        lat = data["results"][0]["geometry"]["lat"]
        lon = data["results"][0]["geometry"]["lng"]
        return lat, lon
    else:
        return None

# Ejemplo de uso
place = "CETis 16, Querétaro"
coordinates = get_coordinates_opencage(place)
print(coordinates)

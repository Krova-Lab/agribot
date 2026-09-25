import os
import requests

def get_soil_data_with_fallback(lat, lon, province_hint=None):
    """
    Query SoilGrids with a short timeout.
    On failure, apply a regional soil-climate fallback profile for Cambodia.
    """
    url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lat={lat}&lon={lon}&property=clay&property=sand&property=phh2o&depth=0-5cm&value=mean"
    
    try:
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            layers = res.json().get("properties", {}).get("layers", [])
            soil_info = {}
            for layer in layers:
                name = layer.get("name")
                val = layer.get("depths", [{}])[0].get("values", {}).get("mean")
                soil_info[name] = val
            soil_info["source"] = "SoilGrids-Live"
            return soil_info
    except Exception as e:
        print(f"[WARNING] SoilGrids timeout/error ({e}). Using regional fallback.")

    # --- REGIONAL FALLBACK (Cambodia) ---
    # If GPS coordinates do not match precisely or the API is unavailable,
    # infer a representative soil texture from the broad geographic area.
    fallback_profiles = {
        "plains": { # Phnom Penh, Kandal, Prey Veng, Kampong Chhnang (Mekong basin)
            "clay": 250, "sand": 350, "phh2o": 58, "source": "Fallback-Regional-Alluvial"
        },
        "west_ricedelta": { # Battambang, Pursat (rice granary)
            "clay": 400, "sand": 200, "phh2o": 62, "source": "Fallback-Regional-Vertisols"
        },
        "highlands": { # Mondulkiri, Ratanakiri (eastern highlands)
            "clay": 450, "sand": 300, "phh2o": 50, "source": "Fallback-Regional-Ferrallitic"
        }
    }

    # Coarse default inference based on latitude/longitude when no clue is available
    # Approximate Phnom Penh centre: Lat 11.55, Lon 104.92
    if lon > 106.0:
        return fallback_profiles["highlands"]
    elif lon < 103.8:
        return fallback_profiles["west_ricedelta"]
    else:
        return fallback_profiles["plains"]

def identify_plant_plantnet(image_path_or_bytes, org_type="auto"):
    """
    Identify a plant through the Pl@ntNet API by sending an image (leaf, flower, fruit, or bark).
    """
    api_key = os.getenv("PLANTNET_API_KEY")
    if not api_key:
        return {"error": "PLANTNET_API_KEY is not configured"}

    url = "https://my-api.plantnet.org/v2/identify/all"
    try:
        if isinstance(image_path_or_bytes, bytes):
            files = [('images', ('image.jpg', image_path_or_bytes, 'image/jpeg'))]
        else:
            with open(image_path_or_bytes, 'rb') as image_file:
                files = [('images', ('image.jpg', image_file, 'image/jpeg'))]
                data = {'organs': [org_type]}
                res = requests.post(url, params={'api-key': api_key}, files=files, data=data, timeout=8)
                return _parse_plantnet_response(res)

        data = {'organs': [org_type]}
        res = requests.post(url, params={'api-key': api_key}, files=files, data=data, timeout=8)
        return _parse_plantnet_response(res)
    except Exception as e:
        print(f"PlantNet error: {type(e).__name__}")
    return {}


def _parse_plantnet_response(response):
    if response.status_code != 200:
        return {}
    results = response.json().get("results", [])
    if not results:
        return {}
    best_match = results[0]
    species = best_match.get("species", {})
    return {
        "scientific_name": species.get("scientificNameWithoutAuthor"),
        "common_names": species.get("commonNames", []),
        "score": round(best_match.get("score", 0) * 100, 1),
    }

if __name__ == "__main__":
    # Test the fallback with a fictional coordinate or simulated outage
    print("Testing the soil client with fallback:")
    data = get_soil_data_with_fallback(11.5564, 104.9282)
    print(data)

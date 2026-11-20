import datetime
import json
import os

FICHIER_JSON = "pointages.json"
CAPACITE_PARKING = 50


def _charger_donnees() -> list:
    if not os.path.exists(FICHIER_JSON):
        return []
    try:
        with open(FICHIER_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _sauvegarder_donnees(donnees: list) -> None:
    with open(FICHIER_JSON, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2)


def enregistrer_entree(plaque: str):
    plaque = plaque.strip()
    if not plaque:
        return False, "Plaque invalide."

    donnees = _charger_donnees()
    for item in reversed(donnees):
        if item.get("plaque") == plaque and item.get("sortie") is None:
            return False, f"Le véhicule ({plaque}) est déjà dans le parking."

    maintenant = datetime.datetime.now().isoformat(timespec="seconds")
    donnees.append(
        {
            "plaque": plaque,
            "entree": maintenant,
            "sortie": None,
        }
    )
    _sauvegarder_donnees(donnees)
    return True, f"Entrée enregistrée pour {plaque} à {maintenant}."


def enregistrer_sortie(plaque: str):
    plaque = plaque.strip()
    if not plaque:
        return False, "Plaque invalide."

    donnees = _charger_donnees()
    for item in reversed(donnees):
        if item.get("plaque") == plaque and item.get("sortie") is None:
            maintenant = datetime.datetime.now().isoformat(timespec="seconds")
            item["sortie"] = maintenant
            _sauvegarder_donnees(donnees)
            return True, f"Sortie enregistrée pour {plaque} à {maintenant}."

    return False, f"Aucune entrée active trouvée pour la plaque {plaque}."


def lister_pointages(plaque: str | None = None, date_str: str | None = None) -> list:
    donnees = _charger_donnees()
    resultats = []

    for item in reversed(donnees):
        p = str(item.get("plaque", ""))
        entree = str(item.get("entree", ""))

        if plaque and plaque.lower() not in p.lower():
            continue
        if date_str and not entree.startswith(date_str):
            continue
        resultats.append(item)

    return resultats


def get_resume_parking(capacite: int = CAPACITE_PARKING):
    donnees = _charger_donnees()
    total_entrees = len(donnees)
    total_sorties = sum(1 for item in donnees if item.get("sortie") is not None)
    vehicules_presents = total_entrees - total_sorties
    places_disponibles = max(0, capacite - vehicules_presents)
    return total_entrees, total_sorties, places_disponibles
   
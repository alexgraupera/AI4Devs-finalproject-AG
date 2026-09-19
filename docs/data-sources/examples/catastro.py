# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx"]
# ///
"""Query the Catastro public web services (OVC): by coordinates, by cadastral reference and by address.

Usage:
    uv run docs/data-sources/examples/catastro.py
"""

from dataclasses import dataclass

import httpx

BASE = "https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero"


class CatastroError(Exception):
    """Business errors come with HTTP 200 and a `lerr` list, e.g. code 5: no property matches."""


@dataclass
class Property:
    cadastral_reference: str  # 20 characters: pc1 + pc2 + car + cc1 + cc2
    use: str  # "Residencial", "Comercial", "Almacen-Estacionamiento"...
    built_surface_m2: int  # BUILT surface (includes common areas), not the usable one
    year_built: int
    address: str


def _get(path: str, params: dict, result_key: str) -> dict:
    response = httpx.get(f"{BASE}/{path}", params=params, timeout=30)
    response.raise_for_status()
    result = response.json()[result_key]
    if result.get("control", {}).get("cuerr"):
        error = result["lerr"][0]
        raise CatastroError(f"[{error['cod']}] {error['des']}")
    return result


def _address(dt: dict) -> str:
    urban = dt["locs"]["lous"]["lourb"]
    street, inner = urban["dir"], urban.get("loint", {})
    floor_door = " ".join(x for x in (inner.get("pt"), inner.get("pu")) if x)
    return " ".join(f"{street['tv']} {street['nv']} {street['pnp']} {floor_door}".split()) + f", {dt['nm']}"


def _properties(result: dict) -> list[Property]:
    # One match comes as `bico.bi`; several matches come as `lrcdnp.rcdnp` (e.g. every flat of a building).
    items = [result["bico"]["bi"] | {"rc": result["bico"]["bi"]["idbi"]["rc"]}] if "bico" in result else result["lrcdnp"]["rcdnp"]
    return [
        Property(
            cadastral_reference="".join(item["rc"][k] for k in ("pc1", "pc2", "car", "cc1", "cc2")),
            use=item["debi"]["luso"],
            built_surface_m2=int(item["debi"]["sfc"]),
            year_built=int(item["debi"]["ant"]),
            address=_address(item["dt"]),
        )
        for item in items
    ]


def reference_by_coordinates(lon: float, lat: float) -> tuple[str, str]:
    """Returns the 14-character parcel reference and its address. Points in the street raise error 16."""
    result = _get(
        "COVCCoordenadas.svc/json/Consulta_RCCOOR",
        {"CoorX": lon, "CoorY": lat, "SRS": "EPSG:4326"},
        "Consulta_RCCOORResult",
    )
    coordinate = result["coordenadas"]["coord"][0]
    return coordinate["pc"]["pc1"] + coordinate["pc"]["pc2"], coordinate["ldt"]


def by_reference(reference: str) -> list[Property]:
    """14 characters (parcel) returns every property of the building; 20 characters returns one property."""
    return _properties(_get("COVCCallejero.svc/json/Consulta_DNPRC", {"RefCat": reference}, "consulta_dnprcResult"))


def by_address(province: str, municipality: str, street_type: str, street: str, number: str) -> list[Property]:
    """Without floor and door it returns every property of the building."""
    params = {"Provincia": province, "Municipio": municipality, "Sigla": street_type, "Calle": street, "Numero": number}
    return _properties(_get("COVCCallejero.svc/json/Consulta_DNPLOC", params, "consulta_dnplocResult"))


if __name__ == "__main__":
    reference, address = reference_by_coordinates(-3.7010, 40.4340)
    print(f"By coordinates -> parcel {reference} ({address})\n")

    flats = [p for p in by_reference(reference) if p.use == "Residencial"]
    print(f"By parcel reference -> {len(flats)} homes, e.g.:")
    for flat in flats[:3]:
        print(" ", flat)

    print(f"\nBy full reference -> {by_reference(flats[0].cadastral_reference)[0]}")

    building = by_address("MADRID", "MADRID", "CL", "QUESADA", "11")
    print(f"\nBy address -> {len(building)} properties in the building")

    try:
        reference_by_coordinates(-3.6920, 40.4290)
    except CatastroError as error:
        print(f"\nPoint in the middle of a street -> CatastroError {error}")

# Catastro public web services (OVC)

Official property data from the Dirección General del Catastro: use, built surface and year of construction of every property. Used as an **agent tool** to check the data declared in a listing.

- **Documentation**: [Servicios web del Catastro](https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/COVCCallejero.svc/help) (REST/JSON variants of the OVC services).
- **Licence**: public, non-protected cadastral data (no owner data is returned).
- **Auth**: none.
- **Example**: [`examples/catastro.py`](examples/catastro.py)

## Endpoints (JSON)

Base: `https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero`

| Endpoint | Input | Returns |
|---|---|---|
| `COVCCoordenadas.svc/json/Consulta_RCCOOR` | `CoorX` (lon), `CoorY` (lat), `SRS=EPSG:4326` | Parcel reference (14 characters) and address |
| `COVCCallejero.svc/json/Consulta_DNPRC` | `RefCat`: 14 characters (parcel) or 20 (one property) | Property data |
| `COVCCallejero.svc/json/Consulta_DNPLOC` | `Provincia`, `Municipio`, `Sigla` (`CL`, `AV`...), `Calle`, `Numero` (+ optional floor/door) | Property data |

### By coordinates

```bash
curl "https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/COVCCoordenadas.svc/json/Consulta_RCCOOR?CoorX=-3.7010&CoorY=40.4340&SRS=EPSG:4326"
```

```json
{"Consulta_RCCOORResult": {"control": {"cucoor": 1}, "coordenadas": {"coord": [
  {"pc": {"pc1": "0663903", "pc2": "VK4706D"},
   "geo": {"xcen": "-3.7010", "ycen": "40.4340", "srs": "EPSG:4326"},
   "ldt": "CL QUESADA 11 MADRID (MADRID)"}]}}}
```

### By cadastral reference

A 14-character reference (parcel) returns every property of the building; 20 characters return a single one.

```bash
curl "https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/COVCCallejero.svc/json/Consulta_DNPRC?RefCat=0663903VK4706D"
```

Several matches come in `lrcdnp.rcdnp` (real response, one item):

```json
{"consulta_dnprcResult": {"control": {"cudnp": 16}, "lrcdnp": {"rcdnp": [
  {"rc": {"pc1": "0663903", "pc2": "VK4706D", "car": "0004", "cc1": "F", "cc2": "X"},
   "dt": {"np": "MADRID", "nm": "MADRID",
          "locs": {"lous": {"lourb": {"dir": {"tv": "CL", "nv": "QUESADA", "pnp": "11"},
                                      "loint": {"pt": "01", "pu": "IZ"}, "dp": "28010"}}}},
   "debi": {"luso": "Residencial", "sfc": "62", "cpt": "...", "ant": "1970"}}
]}}}
```

A single match comes in `bico.bi` instead, with the reference in `bico.bi.idbi.rc`.

| Field | Meaning |
|---|---|
| `rc` | Cadastral reference: `pc1 + pc2 + car + cc1 + cc2` (20 characters) |
| `debi.luso` | Use: `Residencial`, `Comercial`, `Oficinas`, `Almacen-Estacionamiento`... |
| `debi.sfc` | **Built** surface in m² (includes the share of common areas) |
| `debi.ant` | Year of construction |
| `dt...loint.pt` / `pu` | Floor / door |
| `dt...dp` | Postal code |

### By address

```bash
curl "https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/COVCCallejero.svc/json/Consulta_DNPLOC?Provincia=MADRID&Municipio=MADRID&Sigla=CL&Calle=QUESADA&Numero=11"
```

Without floor and door it returns every property of the building (16 in this example), with the same structure as above.

### Errors

Business errors come with **HTTP 200** and a `lerr` list:

```json
{"Consulta_RCCOORResult": {"control": {"cuerr": 1}, "lerr": [{"cod": "16", "des": "PARA ESAS COORDENADAS NO HAY REFERENCIA DISPONIBLE"}]}}
{"consulta_dnprcResult": {"control": {"cuerr": 1}, "lerr": [{"cod": "5", "des": "NO EXISTE NINGÚN INMUEBLE CON LOS PARÁMETROS INDICADOS"}]}}
```

## Python usage

From [`examples/catastro.py`](examples/catastro.py):

```python
def _get(path: str, params: dict, result_key: str) -> dict:
    response = httpx.get(f"{BASE}/{path}", params=params, timeout=30)
    response.raise_for_status()
    result = response.json()[result_key]
    if result.get("control", {}).get("cuerr"):
        error = result["lerr"][0]
        raise CatastroError(f"[{error['cod']}] {error['des']}")
    return result


def by_reference(reference: str) -> list[Property]:
    return _properties(_get("COVCCallejero.svc/json/Consulta_DNPRC", {"RefCat": reference}, "consulta_dnprcResult"))
```

Output:

```
$ uv run docs/data-sources/examples/catastro.py
By coordinates -> parcel 0663903VK4706D (CL QUESADA 11 MADRID (MADRID))

By parcel reference -> 13 homes, e.g.:
  Property(cadastral_reference='0663903VK4706D0004FX', use='Residencial', built_surface_m2=62, year_built=1970, address='CL QUESADA 11 01 IZ, MADRID')
  Property(cadastral_reference='0663903VK4706D0005GM', use='Residencial', built_surface_m2=70, year_built=1970, address='CL QUESADA 11 01 CN, MADRID')
  Property(cadastral_reference='0663903VK4706D0006HQ', use='Residencial', built_surface_m2=150, year_built=1970, address='CL QUESADA 11 02 DR, MADRID')

By full reference -> Property(cadastral_reference='0663903VK4706D0004FX', use='Residencial', built_surface_m2=62, year_built=1970, address='CL QUESADA 11 01 IZ, MADRID')

By address -> 16 properties in the building

Point in the middle of a street -> CatastroError [16] PARA ESAS COORDENADAS NO HAY REFERENCIA DISPONIBLE
```

## How the project uses it

- Tool input: the cadastral reference (the most reliable) or the address with floor and door.
- Checks:
  - **Surface**: the listing usually declares the *usable* surface, Catastro gives the *built* one, which is larger because it includes walls and the share of common areas. Flag only large differences, e.g. usable surface above the built one, or far below it.
  - **Year of construction**: flag contradictions such as "obra nueva" in a 1970 building.
  - **Use**: flag a listing for a home whose property is not `Residencial`.

## Gotchas

- Errors are HTTP 200 with `control.cuerr` and `lerr`: always check them.
- One match (`bico.bi`) and several matches (`lrcdnp.rcdnp`) have different shapes.
- `sfc` is the built surface, not the usable one.
- Coordinates must fall inside a parcel: a point in the street returns error 16.
- Catastro municipality codes (`loine.cm`) are not INE codes: do not use them to join with SERPAVI.
- Cache responses: the data changes rarely and the service is shared.

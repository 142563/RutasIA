"""Datos semilla del grafo nacional: nodos y tramos candidatos.

- NODES: 22 cabeceras + municipios clave + cruces (salidas y fronteras incluidas).
  Coordenadas aproximadas (±1–2 km). Las que llevan "# †" son las menos seguras
  y hay que verificarlas antes de construir el grafo.
- ROAD_SEGMENTS: tramos entre nodos vecinos, sin dirección. `build_graph`
  (Día 2) los verifica con Google Routes API y crea DOS aristas dirigidas por
  tramo. `needs_check=True` = no hay certeza de que la carretera exista tal cual
  o de que no pase por otro nodo del grafo. `road` es informativo: "RN" = ruta
  nacional cuyo número exacto falta confirmar.
"""
from __future__ import annotations

from typing import NamedTuple


class SeedNode(NamedTuple):
    code: str
    name: str
    kind: str  # cabecera | municipio | cruce
    department: str  # código de GuatemalaDepartment
    latitude: float
    longitude: float


class RoadSegment(NamedTuple):
    a: str
    b: str
    road: str
    needs_check: bool = False


NODES: list[SeedNode] = [
    # Guatemala
    SeedNode("ciudad-guatemala", "Ciudad de Guatemala", "cabecera", "GU", 14.6349, -90.5069),
    SeedNode("el-trebol", "El Trébol (CA-1/CA-9)", "cruce", "GU", 14.6195, -90.5310),  # †
    SeedNode("puente-belice", "Salida CA-9 Norte (Puente Belice)", "cruce", "GU", 14.6470, -90.4975),  # †
    SeedNode("salida-ca1-oriente", "Salida CA-1 Oriente (Carretera a El Salvador, km 15)", "cruce", "GU", 14.5740, -90.4730),  # †
    SeedNode("mixco", "Mixco (Calzada Roosevelt)", "municipio", "GU", 14.6333, -90.6064),
    SeedNode("villa-nueva", "Villa Nueva (salida CA-9 Sur)", "municipio", "GU", 14.5269, -90.5875),
    SeedNode("amatitlan", "Amatitlán", "municipio", "GU", 14.4787, -90.6178),
    SeedNode("san-juan-sacatepequez", "San Juan Sacatepéquez", "municipio", "GU", 14.7189, -90.6442),
    SeedNode("san-jose-pinula", "San José Pinula", "municipio", "GU", 14.5461, -90.4114),
    # Sacatepéquez
    SeedNode("antigua-guatemala", "Antigua Guatemala", "cabecera", "SA", 14.5586, -90.7295),
    SeedNode("san-lucas-sacatepequez", "San Lucas Sacatepéquez", "cruce", "SA", 14.6092, -90.6567),
    SeedNode("sumpango", "Sumpango", "municipio", "SA", 14.6453, -90.7347),
    SeedNode("alotenango", "Alotenango", "municipio", "SA", 14.4833, -90.8061),
    # Chimaltenango
    SeedNode("chimaltenango", "Chimaltenango", "cabecera", "CM", 14.6611, -90.8196),
    SeedNode("patzicia", "Patzicía", "municipio", "CM", 14.6317, -90.9269),
    SeedNode("tecpan", "Tecpán Guatemala", "municipio", "CM", 14.7622, -90.9947),
    # Sololá
    SeedNode("solola", "Sololá", "cabecera", "SO", 14.7730, -91.1830),
    SeedNode("los-encuentros", "Los Encuentros", "cruce", "SO", 14.7930, -91.1470),  # †
    SeedNode("panajachel", "Panajachel", "municipio", "SO", 14.7407, -91.1583),
    SeedNode("godinez", "Godínez", "cruce", "SO", 14.7350, -91.0930),  # †
    SeedNode("nahuala", "Nahualá", "municipio", "SO", 14.8436, -91.3181),  # †
    SeedNode("san-lucas-toliman", "San Lucas Tolimán", "municipio", "SO", 14.6333, -91.1417),
    # Totonicapán
    SeedNode("totonicapan", "Totonicapán", "cabecera", "TO", 14.9109, -91.3611),
    SeedNode("cuatro-caminos", "Cuatro Caminos", "cruce", "TO", 14.9090, -91.4390),  # †
    # Quetzaltenango
    SeedNode("quetzaltenango", "Quetzaltenango", "cabecera", "QZ", 14.8347, -91.5181),
    SeedNode("salcaja", "Salcajá", "municipio", "QZ", 14.8819, -91.4583),
    SeedNode("san-juan-ostuncalco", "San Juan Ostuncalco", "municipio", "QZ", 14.8717, -91.6217),
    SeedNode("zunil", "Zunil", "municipio", "QZ", 14.7839, -91.4833),
    SeedNode("coatepeque", "Coatepeque", "municipio", "QZ", 14.7036, -91.8625),
    # San Marcos
    SeedNode("san-marcos", "San Marcos", "cabecera", "SM", 14.9650, -91.7960),
    SeedNode("san-rafael-pie-de-la-cuesta", "San Rafael Pie de la Cuesta", "municipio", "SM", 14.9306, -91.9117),  # †
    SeedNode("malacatan", "Malacatán", "municipio", "SM", 14.9111, -92.0583),
    SeedNode("pajapita", "Pajapita", "cruce", "SM", 14.7200, -92.0333),  # †
    SeedNode("tecun-uman", "Ciudad Tecún Umán (Ayutla, frontera)", "municipio", "SM", 14.6772, -92.1386),
    # Huehuetenango
    SeedNode("huehuetenango", "Huehuetenango", "cabecera", "HU", 15.3197, -91.4709),
    SeedNode("aguacatan", "Aguacatán", "municipio", "HU", 15.3431, -91.3133),
    SeedNode("la-mesilla", "La Mesilla (frontera)", "cruce", "HU", 15.6386, -91.9890),  # †
    SeedNode("soloma", "Soloma", "municipio", "HU", 15.7108, -91.4556),  # †
    SeedNode("barillas", "Santa Cruz Barillas", "municipio", "HU", 15.8028, -91.3122),  # †
    # Quiché
    SeedNode("santa-cruz-del-quiche", "Santa Cruz del Quiché", "cabecera", "QC", 15.0306, -91.1489),
    SeedNode("chichicastenango", "Chichicastenango", "municipio", "QC", 14.9433, -91.1111),
    SeedNode("sacapulas", "Sacapulas", "municipio", "QC", 15.2889, -91.0889),
    SeedNode("nebaj", "Nebaj", "municipio", "QC", 15.4056, -91.1464),
    SeedNode("uspantan", "Uspantán", "municipio", "QC", 15.3461, -90.8697),
    SeedNode("playa-grande", "Playa Grande (Ixcán)", "municipio", "QC", 15.9700, -90.7600),  # †
    # Baja Verapaz
    SeedNode("salama", "Salamá", "cabecera", "BV", 15.1030, -90.3180),
    SeedNode("rabinal", "Rabinal", "municipio", "BV", 15.0864, -90.4903),
    SeedNode("la-cumbre", "La Cumbre (cruce a Salamá, CA-14)", "cruce", "BV", 15.0850, -90.2050),  # †
    SeedNode("purulha", "Purulhá", "municipio", "BV", 15.2367, -90.2358),
    # Alta Verapaz
    SeedNode("coban", "Cobán", "cabecera", "AV", 15.4703, -90.3708),
    SeedNode("san-pedro-carcha", "San Pedro Carchá", "municipio", "AV", 15.4786, -90.3106),
    SeedNode("san-cristobal-verapaz", "San Cristóbal Verapaz", "municipio", "AV", 15.3667, -90.4792),  # †
    SeedNode("tactic", "Tactic", "municipio", "AV", 15.3175, -90.3525),
    SeedNode("chisec", "Chisec", "municipio", "AV", 15.8117, -90.2894),
    SeedNode("raxruha", "Raxruhá", "municipio", "AV", 15.8683, -90.0417),  # †
    SeedNode("fray-bartolome", "Fray Bartolomé de las Casas", "municipio", "AV", 15.8450, -89.8650),  # †
    SeedNode("chahal", "Chahal", "municipio", "AV", 15.7847, -89.5958),  # †
    SeedNode("panzos", "Panzós", "municipio", "AV", 15.3992, -89.6436),
    # Petén
    SeedNode("flores", "Flores", "cabecera", "PE", 16.9300, -89.8920),
    SeedNode("sayaxche", "Sayaxché", "municipio", "PE", 16.5242, -90.1897),
    SeedNode("la-libertad", "La Libertad", "municipio", "PE", 16.7856, -90.1156),
    SeedNode("poptun", "Poptún", "municipio", "PE", 16.3306, -89.4203),
    SeedNode("san-luis", "San Luis", "municipio", "PE", 16.2000, -89.4400),  # †
    SeedNode("dolores", "Dolores", "municipio", "PE", 16.5144, -89.4156),  # †
    SeedNode("ixlu", "Ixlú (El Cruce)", "cruce", "PE", 16.9760, -89.6890),  # †
    SeedNode("melchor-de-mencos", "Melchor de Mencos (frontera)", "municipio", "PE", 17.0667, -89.1500),  # †
    # Izabal
    SeedNode("puerto-barrios", "Puerto Barrios", "cabecera", "IZ", 15.7278, -88.5944),
    SeedNode("morales", "Morales", "municipio", "IZ", 15.4750, -88.8417),
    SeedNode("la-ruidosa", "La Ruidosa (CA-9/CA-13)", "cruce", "IZ", 15.4417, -88.9850),  # †
    SeedNode("los-amates", "Los Amates", "municipio", "IZ", 15.2536, -89.0978),
    SeedNode("rio-dulce", "Río Dulce (Fronteras)", "cruce", "IZ", 15.6572, -88.9975),
    SeedNode("el-estor", "El Estor", "municipio", "IZ", 15.5333, -89.3333),
    SeedNode("modesto-mendez", "Modesto Méndez (CA-13/FTN)", "cruce", "IZ", 15.9040, -89.2600),  # †
    # Zacapa
    SeedNode("zacapa", "Zacapa", "cabecera", "ZA", 14.9722, -89.5306),
    SeedNode("rio-hondo", "Río Hondo (CA-9/CA-10)", "municipio", "ZA", 15.0417, -89.5847),
    SeedNode("teculutan", "Teculután", "municipio", "ZA", 14.9917, -89.7167),
    SeedNode("gualan", "Gualán", "municipio", "ZA", 15.1250, -89.3597),
    # Chiquimula
    SeedNode("chiquimula", "Chiquimula", "cabecera", "CQ", 14.8000, -89.5450),
    SeedNode("vado-hondo", "Vado Hondo (CA-10/CA-11)", "cruce", "CQ", 14.7100, -89.4700),  # †
    SeedNode("esquipulas", "Esquipulas", "municipio", "CQ", 14.5625, -89.3500),
    SeedNode("ipala", "Ipala", "municipio", "CQ", 14.6167, -89.6250),
    SeedNode("el-florido", "El Florido (frontera Honduras)", "cruce", "CQ", 14.8600, -89.1650),  # †
    # El Progreso
    SeedNode("guastatoya", "Guastatoya", "cabecera", "PR", 14.8539, -90.0686),
    SeedNode("sanarate", "Sanarate", "municipio", "PR", 14.7950, -90.1922),
    SeedNode("el-rancho", "El Rancho (CA-9/CA-14)", "cruce", "PR", 14.9220, -90.0080),  # †
    # Jalapa
    SeedNode("jalapa", "Jalapa", "cabecera", "JA", 14.6333, -89.9889),
    SeedNode("monjas", "Monjas", "municipio", "JA", 14.5000, -89.8722),
    SeedNode("mataquescuintla", "Mataquescuintla", "municipio", "JA", 14.5319, -90.1853),
    # Jutiapa
    SeedNode("jutiapa", "Jutiapa", "cabecera", "JU", 14.2917, -89.8958),
    SeedNode("el-progreso-jutiapa", "El Progreso (Jutiapa)", "municipio", "JU", 14.3553, -89.8494),
    SeedNode("asuncion-mita", "Asunción Mita", "municipio", "JU", 14.3314, -89.7089),
    SeedNode("san-cristobal-frontera", "San Cristóbal Frontera", "cruce", "JU", 14.3000, -89.6200),  # †
    SeedNode("pedro-de-alvarado", "Ciudad Pedro de Alvarado (frontera)", "cruce", "JU", 13.7940, -90.1030),  # †
    # Santa Rosa
    SeedNode("cuilapa", "Cuilapa", "cabecera", "SR", 14.2789, -90.2986),
    SeedNode("barberena", "Barberena", "municipio", "SR", 14.3100, -90.3611),
    SeedNode("chiquimulilla", "Chiquimulilla", "municipio", "SR", 14.0858, -90.3789),
    SeedNode("taxisco", "Taxisco", "municipio", "SR", 14.0700, -90.4639),
    # Escuintla
    SeedNode("escuintla", "Escuintla", "cabecera", "ES", 14.3050, -90.7850),
    SeedNode("palin", "Palín", "municipio", "ES", 14.4050, -90.6981),
    SeedNode("masagua", "Masagua", "municipio", "ES", 14.2025, -90.8578),
    SeedNode("puerto-san-jose", "Puerto San José (Puerto Quetzal)", "municipio", "ES", 13.9261, -90.8200),
    SeedNode("siquinala", "Siquinalá", "municipio", "ES", 14.3050, -90.9653),
    SeedNode("santa-lucia-cotzumalguapa", "Santa Lucía Cotzumalguapa", "municipio", "ES", 14.3333, -91.0167),
    # Suchitepéquez
    SeedNode("mazatenango", "Mazatenango", "cabecera", "SU", 14.5344, -91.5030),
    SeedNode("cocales", "Cocales (CA-2/RN-11)", "cruce", "SU", 14.4100, -91.1450),  # †
    # Retalhuleu
    SeedNode("retalhuleu", "Retalhuleu", "cabecera", "RE", 14.5361, -91.6778),
    SeedNode("champerico", "Champerico", "municipio", "RE", 14.2931, -91.9139),
    SeedNode("el-zarco", "El Zarco (CITO-180)", "cruce", "RE", 14.6300, -91.5870),  # †
]


def _chain(road: str, *codes: str, needs_check: bool = False) -> list[RoadSegment]:
    """Convierte un corredor A → B → C en los tramos A–B y B–C."""
    return [RoadSegment(a, b, road, needs_check) for a, b in zip(codes, codes[1:])]


ROAD_SEGMENTS: list[RoadSegment] = [
    # Capital: calzadas, Periférico y salidas
    RoadSegment("ciudad-guatemala", "el-trebol", "Urbano"),
    RoadSegment("ciudad-guatemala", "puente-belice", "Urbano"),
    RoadSegment("ciudad-guatemala", "salida-ca1-oriente", "Urbano"),
    RoadSegment("el-trebol", "salida-ca1-oriente", "Urbano"),
    RoadSegment("el-trebol", "villa-nueva", "CA-9"),
    RoadSegment("el-trebol", "mixco", "CA-1"),
    RoadSegment("mixco", "san-juan-sacatepequez", "RN-5"),
    RoadSegment("salida-ca1-oriente", "san-jose-pinula", "RN"),
    # CA-1 Occidente (Interamericana)
    *_chain("CA-1", "mixco", "san-lucas-sacatepequez", "sumpango", "chimaltenango", "patzicia", "tecpan",
            "los-encuentros", "nahuala", "cuatro-caminos", "huehuetenango", "la-mesilla"),
    # RN-1 / RN-11 (Atitlán)
    *_chain("RN-1", "los-encuentros", "solola", "panajachel", "godinez"),
    RoadSegment("godinez", "patzicia", "RN", needs_check=True),  # vía Patzún
    *_chain("RN-11", "godinez", "san-lucas-toliman", "cocales"),
    # Altiplano occidental
    *_chain("RN-1", "cuatro-caminos", "salcaja", "quetzaltenango"),
    RoadSegment("cuatro-caminos", "totonicapan", "RN-1"),
    *_chain("RN-1", "quetzaltenango", "san-juan-ostuncalco", "san-marcos"),
    *_chain("CITO-180", "quetzaltenango", "zunil", "el-zarco"),
    RoadSegment("el-zarco", "retalhuleu", "CITO-180"),
    RoadSegment("el-zarco", "mazatenango", "RN", needs_check=True),
    RoadSegment("quetzaltenango", "coatepeque", "RN", needs_check=True),  # vía Colomba
    # San Marcos
    *_chain("RN-1", "san-marcos", "san-rafael-pie-de-la-cuesta", "malacatan"),
    RoadSegment("malacatan", "pajapita", "RN", needs_check=True),
    # CA-2 Occidente (Pacífico)
    *_chain("CA-2", "escuintla", "siquinala", "santa-lucia-cotzumalguapa", "cocales", "mazatenango",
            "retalhuleu", "coatepeque", "pajapita", "tecun-uman"),
    RoadSegment("retalhuleu", "champerico", "RN"),
    # CA-9 Sur
    *_chain("CA-9", "villa-nueva", "amatitlan", "palin", "escuintla", "masagua", "puerto-san-jose"),
    # RN-10 / RN-14 (Sacatepéquez)
    RoadSegment("san-lucas-sacatepequez", "antigua-guatemala", "RN-10"),
    RoadSegment("antigua-guatemala", "chimaltenango", "RN-14"),  # vía Parramos
    *_chain("RN-14", "antigua-guatemala", "alotenango", "escuintla"),
    # CA-2 Oriente
    *_chain("CA-2", "escuintla", "taxisco", "chiquimulilla", "pedro-de-alvarado"),
    RoadSegment("chiquimulilla", "cuilapa", "RN", needs_check=True),
    # CA-1 Oriente
    *_chain("CA-1", "salida-ca1-oriente", "barberena", "cuilapa", "jutiapa", "el-progreso-jutiapa",
            "asuncion-mita", "san-cristobal-frontera"),
    # Jalapa
    *_chain("RN-18", "san-jose-pinula", "mataquescuintla", "jalapa"),
    RoadSegment("sanarate", "jalapa", "RN-19"),
    *_chain("RN", "jalapa", "monjas", "el-progreso-jutiapa"),
    # CA-9 Norte (Atlántico)
    *_chain("CA-9", "puente-belice", "sanarate", "guastatoya", "el-rancho", "teculutan", "rio-hondo",
            "gualan", "los-amates", "la-ruidosa", "morales", "puerto-barrios"),
    # CA-10 / CA-11 (oriente)
    *_chain("CA-10", "rio-hondo", "zacapa", "chiquimula", "vado-hondo", "esquipulas"),
    RoadSegment("vado-hondo", "el-florido", "CA-11"),
    RoadSegment("chiquimula", "ipala", "RN"),
    RoadSegment("ipala", "jalapa", "RN", needs_check=True),
    RoadSegment("ipala", "asuncion-mita", "RN", needs_check=True),
    # CA-14 (Verapaces)
    *_chain("CA-14", "el-rancho", "la-cumbre", "purulha", "tactic", "coban", "san-pedro-carcha"),
    *_chain("RN-17", "la-cumbre", "salama", "rabinal"),
    RoadSegment("rabinal", "san-juan-sacatepequez", "RN-5", needs_check=True),
    # RN-7E (Polochic)
    *_chain("RN-7E", "tactic", "panzos", "el-estor", "rio-dulce"),
    # CA-13 (Petén)
    *_chain("CA-13", "la-ruidosa", "rio-dulce", "modesto-mendez", "san-luis", "poptun", "dolores", "flores"),
    RoadSegment("dolores", "ixlu", "CA-13", needs_check=True),
    *_chain("CA-13", "flores", "ixlu", "melchor-de-mencos"),
    RoadSegment("flores", "la-libertad", "RN"),
    # RN-5 Norte / Franja Transversal del Norte
    *_chain("RN-5", "coban", "chisec", "raxruha", "sayaxche", "flores"),
    *_chain("FTN", "raxruha", "fray-bartolome", "chahal", "modesto-mendez"),
    RoadSegment("chisec", "playa-grande", "FTN", needs_check=True),
    RoadSegment("playa-grande", "uspantan", "RN-7W", needs_check=True),
    RoadSegment("barillas", "playa-grande", "FTN", needs_check=True),
    # RN-15 / RN-7W (Quiché)
    *_chain("RN-15", "los-encuentros", "chichicastenango", "santa-cruz-del-quiche", "sacapulas", "nebaj"),
    *_chain("RN-7W", "sacapulas", "aguacatan", "huehuetenango"),
    *_chain("RN-7W", "sacapulas", "uspantan", "san-cristobal-verapaz", "coban"),
    *_chain("RN-9N", "huehuetenango", "soloma", "barillas"),
]

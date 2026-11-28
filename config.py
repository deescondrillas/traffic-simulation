# A01739410 – Franco De Escondrillas
# A01739769 – Enrique Jiménez
# 2026-11-30

from math import cos, pi, radians
from pathlib import Path

ROOT = Path(__file__).resolve().parent   # rutas absolutas: funcionan desde cualquier carpeta (p. ej. notebooks/)

# --- Semáforo (modelo 3D) ---
TRAFFIC_LIGHT_OBJ = str(ROOT / "assets/traffic_light/traffic_light.obj")
TRAFFIC_LIGHT_HEIGHT = 6.0  # m, altura del poste ya escalado

# El OBJ no trae .mtl: cada foco se reconoce por el color de vértice con que se exportó
LAMP_MESH_COLORS = {
    "red": (0.847059, 0.376471, 0.376471),
    "yellow": (0.941176, 0.984314, 0.419608),
    "green": (0.423529, 1.0, 0.898039),
}
LAMP_COLOR_TOLERANCE = 1e-3
LAMP_ON_COLORS = {
    "red": (1.0, 0.12, 0.08),
    "yellow": (1.0, 0.85, 0.1),
    "green": (0.15, 1.0, 0.6),
}
GREEN_BLINK_PERIOD = 0.5    # s que dura cada encendido y cada apagado del verde parpadeante
LAMP_OFF_FACTOR = 0.25      # brillo de un foco apagado respecto a su color original
LAMP_HALO_SCALE = 1.5       # radio del halo respecto al radio del foco
LAMP_HALO_ALPHA = 0.6       # opacidad del halo en su centro
LAMP_HALO_SEGMENTS = 24
LAMP_HALO_OFFSET = -0.15    # m delante de la cara frontal, para no pelear con el z-buffer

# --- Mapa ---
ROAD_GRAPH = str(ROOT / "assets/arc_de_triomphe/road_graph.json")
MAP_OBJ = str(ROOT / "assets/arc_de_triomphe/arc_de_triomphe.obj")

# --- Semáforos del anillo exterior ---
# Uno por aproximación a cada cruce avenida–anillo: "ring" (el anillo antes del cruce),
# "merge" (el radio que sale de la Étoile) y "outside" (la avenida que llega desde fuera).
# (x, z): base del poste en m. Rumbo: hacia dónde avanzan los coches que lo ven, en grados
# (0 = este, 90 = norte, antihorario); los focos miran en sentido contrario.
TRAFFIC_LIGHTS = (
    # avenida                     aproximación      x        z    rumbo
    ("Avenue de Friedland",       "ring",       167.0,   -11.5,    96.6),
    ("Avenue de Friedland",       "merge",      157.0,   -11.0,     9.7),
    ("Avenue de Friedland",       "outside",    165.0,   -31.0,  -170.3),
    ("Avenue Hoche",              "ring",       146.0,   -85.0,   120.0),
    ("Avenue Hoche",              "merge",      137.0,   -80.0,    32.6),
    ("Avenue Hoche",              "outside",    138.0,   -95.0,  -147.5),
    ("Avenue de Wagram",          "ring",        79.0,  -149.0,   153.6),
    ("Avenue de Wagram",          "merge",       74.0,  -141.0,    64.7),
    ("Avenue de Wagram",          "outside",     62.0,  -157.0,  -115.3),
    ("Avenue Mac-Mahon",          "ring",       -15.0,  -169.0,  -174.5),
    ("Avenue Mac-Mahon",          "outside",    -28.0,  -168.0,   -83.3),
    ("Avenue Carnot",             "ring",       -86.0,  -149.0,  -148.5),
    ("Avenue Carnot",             "merge",      -84.0,  -141.0,   118.8),
    ("Avenue Carnot",             "outside",    -95.0,  -144.0,   -61.2),
    ("Avenue de la Grande Armée", "ring",      -155.0,   -82.0,  -118.1),
    ("Avenue de la Grande Armée", "merge",     -146.0,   -77.0,   154.6),
    ("Avenue de la Grande Armée", "outside",   -162.0,   -65.0,   -25.8),
    ("Avenue Foch",               "ring",      -174.0,    16.0,   -83.1),
    ("Avenue Foch",               "merge",     -164.0,    15.0,  -170.4),
    ("Avenue Foch",               "outside",   -172.0,    31.0,     9.6),
    ("Avenue Victor Hugo",        "ring",      -150.0,    88.0,   -55.2),
    ("Avenue Victor Hugo",        "merge",     -142.0,    83.0,  -147.2),
    ("Avenue Victor Hugo",        "outside",   -143.0,   100.0,    32.8),
    ("Avenue Kléber",             "ring",       -84.0,   156.0,   -22.8),
    ("Avenue Kléber",             "merge",      -79.0,   145.0,  -116.0),
    ("Avenue Kléber",             "outside",    -72.0,   162.0,    63.8),
    ("Avenue d'Iéna",             "ring",         1.0,   172.0,   -10.0),
    ("Avenue d'Iéna",             "merge",        5.0,   164.0,   -83.7),
    ("Avenue d'Iéna",             "outside",     23.0,   171.0,    97.3),
    ("Avenue Marceau",            "ring",        80.0,   153.0,    29.3),
    ("Avenue Marceau",            "merge",       75.0,   144.0,   -61.1),
    ("Avenue des Champs-Élysées", "ring",       147.0,    84.5,    62.3),
    ("Avenue des Champs-Élysées", "merge",      138.0,    79.0,   -25.6),
    ("Avenue des Champs-Élysées", "outside",    154.0,    67.0,   154.4),
)

# --- Simulación ---
SIM_DT = 0.1        # s
SEED = 1
N_CARS = 100       # se prueba siempre con N ≤ 100: con más, el desvío por la Étoile puede atascar la red
DRIVERS_FILE = str(ROOT / "training/training.json")   # conteos del curso de manejo (los escribe train.ipynb)

# --- Red vial ---
RESAMPLE_STEP = 0.5                 # m entre puntos de cada carril
SPIKE_COS = cos(radians(60.0))      # un giro mayor a 60° entre dos puntos es un traslape de OSM
ETOILE_LANES = 5
SPOKE_AVENUES = (                   # las 12 calles, de la 1 a la 12 en sentido antihorario
    "Avenue de Friedland", "Avenue Hoche", "Avenue de Wagram", "Avenue Mac-Mahon",
    "Avenue Carnot", "Avenue de la Grande Armée", "Avenue Foch", "Avenue Victor Hugo",
    "Avenue Kléber", "Avenue d'Iéna", "Avenue Marceau", "Avenue des Champs-Élysées",
)
N_STREETS = len(SPOKE_AVENUES)
# El anillo exterior (Tilsitt/Presbourg) es un círculo ajustado a la calle dibujada en el mapa:
# no está centrado en el Arco, y uno centrado en el origen se saldría hasta 4.6 m de la calle.
OUTER_RING_CENTER = (-3.25, 1.6)    # (x, z) en m
OUTER_RING_RADIUS = 166.9           # m
SPOKE_RADIUS_BAND = (80.0, 160.0)   # m: un tramo de avenida es radio si cruza esta banda
SPOKE_CLIP = 6.0                    # m que se recorta cada radio antes del anillo exterior
MERGE_OFFSET = 12.0                 # m sobre el anillo exterior entre el punto más cercano al radio y la incorporación
DIVERGE_OFFSET = 12.0               # m sobre el anillo exterior entre la separación y el punto más cercano al radio
ETOILE_SPOKE_CLIP = 5.0             # m que se recorta cada radio antes de la Étoile
ETOILE_TURN_OFFSET = 6.0            # m sobre el carril 0 de la Étoile entre el punto más cercano al radio y la unión
HERMITE_TANGENT = 1.0               # magnitud de las tangentes de la curva, en múltiplos de la cuerda
HERMITE_MIN_POINTS = 8
MAX_POINT_GAP = 1.0                 # m, comprobación §5.6
MAX_HEADING_BREAK = radians(10.0)
LOOP_TURN_TOLERANCE = 0.05          # rad: un carril cerrado debe girar 2π

# --- Coches e IDM ---
MAX_SPEED = 50 / 3.6     # m/s
START_SPEED = MAX_SPEED / 2
CAR_LENGTH = 4.5         # m
IDM_A = 1.5              # m/s², aceleración máxima
IDM_B = 2.0              # m/s², frenado cómodo
IDM_T = 1.2              # s, tiempo de seguimiento
IDM_S0 = 2.0             # m, distancia mínima en alto
IDM_DELTA = 4
MIN_GAP = 0.5            # m: por debajo se frena de golpe
LOOKAHEAD = 120.0        # m que mira hacia adelante un coche
STOP_EPS = 0.5           # m/s: por debajo un coche se considera detenido
SPAWN_MARGIN = 5.0       # m libres al inicio y al final de cada radio al repartir coches
SPAWN_SPACING = CAR_LENGTH + 2 * IDM_S0 + 3.0   # m entre coches al repartirlos

# --- Ruta ---
# Si el destino queda a más de estas calles por el anillo exterior, el coche avanza a la siguiente
# calle que entra (1 o 2) y cruza por la Étoile. None = siempre por el anillo exterior.
ETOILE_DETOUR = 5

# --- Étoile: carriles ---
LANE_BY_STREETS = (2, 5, 8, 10)     # calles que hay que avanzar para usar el 2.º, 3.º, 4.º y 5.º carril
LANE_CHANGE_ARC = 2 * pi / 12       # rad que se reservan por carril para volver al 0
GAP_FRONT = 8.0          # m libres adelante para cambiar de carril
GAP_BACK = 10.0          # m libres atrás para cambiar de carril
LANE_CHANGE_TIME = 2.0   # s

# --- Étoile: juego de dos roles ---
WARMUP_ROUNDS = 60       # rondas del curso de manejo (0 = conductores novatos)
RETRY_TIME = 1.5         # s antes de volver a jugar si los dos frenaron o los dos siguieron
T_CONFLICT = 4.0         # s: un coche de la glorieta que llega antes es rival
MIN_RIVAL_DIST = 10.0    # m antes de la curva del entrante: más cerca ya no se juega, se espera
DECISION_DIST = 30.0     # m antes de la línea de ceda en que el entrante decide
YIELD_BACK = 4.0         # m detrás de la proyección del entrante donde se detiene quien cede
YIELD_DECEL = 4.0        # m/s²: si tendría que frenar más fuerte, el de la glorieta pasa sin jugar
YIELD_TIMEOUT = 6.0      # s máximos que cede un coche de la glorieta (evita esperas eternas)
EXIT_SPACE = 15.0        # m libres que necesita el radio de salida para entrar a la Étoile

# --- Semáforos BDI ---
APPROACH_DIST = 60.0     # m antes de la línea de alto en que los coches mandan INFORM
LIGHT_STOP_BACK = 6.0    # m antes de la curva del radio donde se detiene el anillo
CYCLE_TIME = 40.0        # s de verde a repartir entre las dos fases
MIN_GREEN = 6.0          # s
MAX_EXTENSION = 10.0     # s
BLINK_TIME = 2.0         # s de verde parpadeante antes del amarillo
YELLOW_TIME = 2.0

# --- Coche (modelo 3D) ---
# Medidas en unidades del .obj ya con swapyz: X = largo (frente +X), Y = alto, Z = ancho
CAR_DIR = str(ROOT / "assets/car")
CAR_PARTS = ("carroceria.obj", "llanta_FL.obj", "llanta_FR.obj", "llantas_traseras.obj")
CAR_HUES = 12                       # tonos de carrocería distintos (0 = el rojo del .mtl)
CAR_MESH_LENGTH = 9.85              # largo de la carrocería en unidades del .obj
CAR_SCALE = CAR_LENGTH / CAR_MESH_LENGTH
TIRE_RADIUS = 0.71
REAR_AXLE = (-2.5, -0.5, 0.0)       # centro de llantas_traseras.obj
FRONT_TIRE = (3.35, -0.5, 1.6)      # llanta delantera izquierda; la derecha es espejo en Z
WHEELBASE = (FRONT_TIRE[0] - REAR_AXLE[0]) * CAR_SCALE   # m
ROAD_Y = 0.15                       # m, superficie de las calles en el mapa
# Luces del coche: (x, y, z) en unidades del .obj, una por lado (espejo en Z)
TAIL_LAMP = (-4.62, 0.5, 1.15)
FRONT_LAMP = (5.05, 0.3, 1.3)
CAR_LAMP_SIZE = 0.25                # medio lado del cuadro, en unidades del .obj
BRAKE_COLOR = (1.0, 0.05, 0.05)
BLINKER_COLOR = (1.0, 0.6, 0.0)
BLINKER_PERIOD = 0.4                # s encendido y s apagado

# --- Ventana y cámara ---
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
FPS = 60
FOVY = 45.0
ZNEAR = 1.0
ZFAR = 2000.0
CLEAR_COLOR = (0.55, 0.62, 0.7, 1.0)
CAMERA_TARGET = (0.0, 25.0, 0.0)  # m, el Arco
CAMERA_START_DISTANCE = 416.0     # m del ojo al objetivo
CAMERA_MIN_DISTANCE = 20.0
CAMERA_MAX_DISTANCE = 1200.0      # por debajo de ZFAR para no recortar la ciudad
CAMERA_START_ELEVATION = 33.0     # grados sobre el horizonte del objetivo
CAMERA_MAX_ELEVATION = 89.0       # a 90° la vista coincide con el vector "arriba" de gluLookAt
CAMERA_MIN_HEIGHT = 2.0           # m: el ojo nunca baja del piso
ORBIT_STEP = 1.0    # grados por cuadro
AUTO_ORBIT_STEP = ORBIT_STEP / 5
ELEVATION_STEP = 0.5  # grados por cuadro
ZOOM_FACTOR = 1.02    # la distancia se multiplica o divide por esto en cada cuadro

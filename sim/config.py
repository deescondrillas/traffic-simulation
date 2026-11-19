# A01739410 – Franco De Escondrillas
# A01739769 – Enrique Jiménez
# 2026-11-18

# --- Semáforo (modelo 3D) ---
TRAFFIC_LIGHT_OBJ = "assets/traffic_light.obj"
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
MAP_OBJ = "assets/arc_de_triomphe/arc_de_triomphe.obj"

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
SIM_DT = 0.1  # s

# --- Ciclo fijo de semáforos (provisional hasta TrafficLightAgent) ---
RING_GREEN_TIME = 20.0   # s de verde fijo para el anillo
MERGE_GREEN_TIME = 10.0  # s de verde fijo para el radio que se incorpora
BLINK_TIME = 3.0         # s de verde parpadeante antes del amarillo
YELLOW_TIME = 3.0

# --- Ventana y cámara ---
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
FPS = 60
FOVY = 45.0
ZNEAR = 1.0
ZFAR = 2000.0
CLEAR_COLOR = (0.55, 0.62, 0.7, 1.0)
CAMERA_TARGET = (0.0, 25.0, 0.0)  # m, el Arco
CAMERA_ORBIT_RADIUS = 350.00
CAMERA_START_HEIGHT = 250.0
CAMERA_MIN_HEIGHT = 2.0
ORBIT_STEP = 1.0    # grados por cuadro
AUTO_ORBIT_STEP = ORBIT_STEP / 5
HEIGHT_STEP = 3.0   # m por cuadro

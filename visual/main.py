import pygame
from pygame.locals import *

# Cargamos las bibliotecas de OpenGL
from OpenGL.GL import *
from OpenGL.GLU import *

import os
import math

from Car import Car, CAR_MODELS
from objLoader import OBJ

screen_width = 1400
screen_height = 800
#vc para el obser.
FOVY=60.0
ZNEAR=0.5
ZFAR=1500.0
#Variables para definir la posicion del observador (vista general)
#gluLookAt(EYE_X,EYE_Y,EYE_Z,CENTER_X,CENTER_Y,CENTER_Z,UP_X,UP_Y,UP_Z)
EYE_X = 180.0
EYE_Y = 170.0
EYE_Z = 230.0
CENTER_X = 0
CENTER_Y = 0
CENTER_Z = 0
UP_X=0
UP_Y=1
UP_Z=0

# ---------------- Mapa: glorieta del Arco del Triunfo ----------------
# El .obj ya viene en metros, Y arriba, origen en el Arco, +X este, -Z norte
# (por eso se carga SIN swapyz).
MAP_FILE = os.path.join("arc_de_triomphe", "arc_de_triomphe.obj")
ROAD_Y = 0.15  # altura de la superficie de las calles en el .obj

# Centros (x, z) y radios ajustados a los carriles de road_graph.json.
# Las dos glorietas giran antihorario visto desde arriba (se maneja por la derecha).
INNER_CENTER = (-2.37, 0.94)                     # Place Charles de Gaulle
INNER_LANES = [73.97, 71.27, 68.57, 65.85, 63.16]  # un carro por carril
OUTER_CENTER = (-3.2, 2.05)                      # Rue de Tilsitt / Rue de Presbourg
OUTER_RADIUS = 166.87
OUTER_CARS = 4

# Linea recta: un carril de los Champs-Elysees (x, z)
LINE_START = (60.0, 38.1)
LINE_END = (366.3, 185.4)

# Carro del jugador: en la Avenue Marceau, justo enfrente de la camara,
# viendo hacia la glorieta
PLAYER_START = (82.1, 142.6)
PLAYER_RY = 118.4  # grados

# ---------------- Carros ----------------
CAR_TYPE = "mustang"
CAR_SCALE = 0.5  # el .obj mide ~9.85 de largo -> ~4.9 m
CAR_VEL = 0.4    # metros por frame (~40 km/h a ~30 fps)

# Ruta absoluta a assets/, independiente del directorio desde donde se ejecute
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")

city_map = None
cars = []          # todos los carros (se actualizan y dibujan)
player = None      # el carro que se maneja con el teclado
chase_cam = False  # tecla V: camara siguiendo al jugador

pygame.init()

def Init():
    global city_map, player
    pygame.display.set_mode(
        (screen_width, screen_height), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Simulacion de trafico")

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(FOVY, screen_width/screen_height, ZNEAR, ZFAR)

    glMatrixMode(GL_MODELVIEW)
    glClearColor(0.55, 0.7, 0.85, 1.0)  # cielo
    glEnable(GL_DEPTH_TEST)

    glLightfv(GL_LIGHT0, GL_AMBIENT, (0.5, 0.5, 0.5, 1.0))
    glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.6, 0.6, 0.6, 1.0))
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL)
    glEnable(GL_NORMALIZE)  # los carros usan glScalef; sin esto la luz falla

    # Mapa (tarda unos segundos: ~100k caras)
    print("Cargando mapa...")
    city_map = OBJ(os.path.join(ASSETS_DIR, MAP_FILE), swapyz=False)

    # Piezas del carro: se cargan una vez y todos los carros las comparten
    spec = CAR_MODELS[CAR_TYPE]
    parts = [OBJ(os.path.join(ASSETS_DIR, spec["folder"], p), swapyz=True)
             for p in spec["parts"]]

    def newCar():
        c = Car(CAR_VEL, CAR_SCALE, [0.0, 0.0, 0.0], CAR_TYPE, parts)
        c.pos[1] = ROAD_Y + c.groundOffset * c.Scale  # llantas sobre la calle
        cars.append(c)
        return c

    # Glorieta interior: un carro por carril, repartidos
    for i, radius in enumerate(INNER_LANES):
        newCar().setCircle(INNER_CENTER, radius, theta=i * 2.0 * math.pi / len(INNER_LANES))

    # Glorieta exterior
    for i in range(OUTER_CARS):
        newCar().setCircle(OUTER_CENTER, OUTER_RADIUS, theta=i * 2.0 * math.pi / OUTER_CARS)

    # Carro en linea recta
    newCar().setLine(LINE_START, LINE_END)

    # Carro del jugador (empieza quieto, se maneja con el teclado)
    player = newCar()
    player.pos[0], player.pos[2] = PLAYER_START
    player.Body_ry = PLAYER_RY

def setCamera():
    glLoadIdentity()
    if chase_cam:
        p = player
        d = p.Direction
        gluLookAt(p.pos[0] - 14 * d[0], p.pos[1] + 6, p.pos[2] - 14 * d[2],
                  p.pos[0] + 10 * d[0], p.pos[1], p.pos[2] + 10 * d[2],
                  0, 1, 0)
    else:
        gluLookAt(EYE_X,EYE_Y,EYE_Z,CENTER_X,CENTER_Y,CENTER_Z,UP_X,UP_Y,UP_Z)
    # La luz se fija despues de la camara para que quede fija en el mundo
    glLightfv(GL_LIGHT0, GL_POSITION, (0.3, 1.0, 0.5, 0.0))

def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    setCamera()

    # Se dibuja el mapa
    city_map.render()

    # Se dibujan los carros
    for car in cars:
        car.update()
        car.draw()

done = False
Init()
while not done:
    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                done = True
            # Controles del jugador (cada pulsacion = 5 grados de direccion)
            elif event.key == pygame.K_SPACE:
                player.toggleMove()
            elif event.key == pygame.K_LEFT:
                player.setRotate('left')
            elif event.key == pygame.K_RIGHT:
                player.setRotate('right')
            elif event.key == pygame.K_c:
                player.setRotate('center')
            # V: cambiar entre vista general y camara siguiendo al jugador
            elif event.key == pygame.K_v:
                chase_cam = not chase_cam
        elif event.type == pygame.QUIT:
            done = True

    display()

    pygame.display.flip()
    pygame.time.wait(10)

pygame.quit()

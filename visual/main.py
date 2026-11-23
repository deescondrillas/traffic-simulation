import pygame
from pygame.locals import *

# Cargamos las bibliotecas de OpenGL
from OpenGL.GL import *
from OpenGL.GLU import *

import os

from Car import Car, CAR_MODELS
from objLoader import OBJ

screen_width = 1400
screen_height = 800
#vc para el obser.
FOVY=60.0
ZNEAR=1.0
ZFAR=900.0
#Variables para definir la posicion del observador
#gluLookAt(EYE_X,EYE_Y,EYE_Z,CENTER_X,CENTER_Y,CENTER_Z,UP_X,UP_Y,UP_Z)
EYE_X = 250.0
EYE_Y = 150.0
EYE_Z = 250.0
CENTER_X = 0
CENTER_Y = 0
CENTER_Z = 0
UP_X=0
UP_Y=1
UP_Z=0

DimBoard = 200.0
FLOOR_Y = -20.0  # altura del plano gris
cars = []
# Circulo exacto (tecla O): centro (x, z) y radio alpha
CIRCLE_CENTER = (0.0, 0.0)
CIRCLE_ALPHA = 120.0
# Cuantos carros de cada tipo (los tipos se definen en CAR_MODELS, en Car.py)
n_cars = {
    "mustang": 1
}
# Ruta absoluta a assets/, independiente del directorio desde donde se ejecute
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")

pygame.init()

def Init():
    pygame.display.set_mode(
        (screen_width, screen_height), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Simulacion de trafico")

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(FOVY, screen_width/screen_height, ZNEAR, ZFAR)

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    gluLookAt(EYE_X,EYE_Y,EYE_Z,CENTER_X,CENTER_Y,CENTER_Z,UP_X,UP_Y,UP_Z)
    glClearColor(0,0,0,0)
    glEnable(GL_DEPTH_TEST)

    glLightfv(GL_LIGHT0, GL_POSITION,  (0, 200, 0, 0.0))
    glLightfv(GL_LIGHT0, GL_AMBIENT, (0.5, 0.5, 0.5, 1.0))
    glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.5, 0.5, 0.5, 1.0))
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL)

    for car_type, count in n_cars.items():
        # Cargar las piezas una sola vez por tipo (OBJ las compila al cargarlas)
        spec = CAR_MODELS[car_type]
        parts = [OBJ(os.path.join(ASSETS_DIR, spec["folder"], p), swapyz=True)
                 for p in spec["parts"]]

        # Una instancia de Car por cada coche, compartiendo la geometria
        for i in range(count):
            pos = [0.0, 0.0, i * 30.0]  # separacion provisional
            c = Car(1.0, 10.0, pos, car_type, parts)
            # Apoyar las llantas sobre el plano (que esta en y = FLOOR_Y)
            c.pos[1] = FLOOR_Y + c.groundOffset * c.Scale
            cars.append(c)

def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    #Se dibuja el plano gris
    glColor3f(0.3, 0.3, 0.3)
    glBegin(GL_QUADS)
    glVertex3d(-DimBoard, FLOOR_Y, -DimBoard)
    glVertex3d(-DimBoard, FLOOR_Y, DimBoard)
    glVertex3d(DimBoard, FLOOR_Y, DimBoard)
    glVertex3d(DimBoard, FLOOR_Y, -DimBoard)
    glEnd()

    # Se dibuja el carro
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
            # Controles del carro (cada pulsacion = 5 grados de direccion)
            elif event.key == pygame.K_SPACE:
                for car in cars:
                    car.toggleMove()
            elif event.key == pygame.K_LEFT:
                for car in cars:
                    car.setRotate('left')
            elif event.key == pygame.K_RIGHT:
                for car in cars:
                    car.setRotate('right')
            elif event.key == pygame.K_c:
                for car in cars:
                    car.setRotate('center')
            # O: activar/desactivar circulo exacto alrededor de CIRCLE_CENTER
            elif event.key == pygame.K_o:
                for car in cars:
                    if car.circle is None:
                        car.setCircle(CIRCLE_CENTER, CIRCLE_ALPHA, 'left')
                    else:
                        car.clearCircle()
        elif event.type == pygame.QUIT:
            done = True

    display()

    pygame.display.flip()
    pygame.time.wait(10)

pygame.quit()

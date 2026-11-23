from OpenGL.GL import *

import numpy as np
import math

# Todo lo que depende del modelo 3D. Para agregar un carro: agregar una entrada.
# Medidas en unidades del .obj (con swapyz): X = largo (frente +X), Y = alto, Z = ancho
CAR_MODELS = {
    "mustang": {
        "folder": "car",
        "parts": ["carroceria.obj", "llanta_FL.obj", "llanta_FR.obj", "llantas_traseras.obj"],
        "tire_radius": 0.71,
        "rear_axle":  (-2.5, -0.5, 0.0),   # centro de llantas_traseras.obj
        "front_tire": (3.35, -0.5, 1.6),   # llanta delantera izquierda; la derecha es espejo en Z
    },
}

# Indices de las piezas dentro de la lista de componentes
# (mismo orden que "parts" en CAR_MODELS)
BODY, TIRE_FL, TIRE_FR, TIRES_BACK = 0, 1, 2, 3


class Car:

    def __init__(self, vel, scale, pos, type, parts):
        spec = CAR_MODELS[type]  # un tipo desconocido da KeyError
        self.vel = vel
        self.Scale = scale
        self.pos = np.array(pos, dtype=np.float64)
        self.type = type
        self.component = parts

        # Centro de cada llanta en coordenadas del modelo
        self.tire_BaseRadius = spec["tire_radius"]
        self.tireT_pos = np.array(spec["rear_axle"])
        self.tireFL_pos = np.array(spec["front_tire"])
        self.tireFR_pos = self.tireFL_pos * [1, 1, -1]

        # Distancia del origen del modelo al piso (parte baja de la llanta)
        self.groundOffset = -self.tireT_pos[1] + self.tire_BaseRadius
        # Distancia entre ejes (escalada)
        self.L = abs(self.tireFL_pos[0] - self.tireT_pos[0]) * self.Scale

        # Vector de direccion (plano XZ); update() lo recalcula desde Body_ry
        self.Direction = np.array([1.0, 0.0, 0.0])
        self.Moving = False

        self.Body_ry = 0.0
        self.T1_F_ry = 0.0     # giro (direccion) de las llantas frontales
        self.MAX_STEER = 35.0  # angulo maximo de direccion (grados)

        # theta = (360 * d) / (2*pi*r); negativo para que giren hacia adelante
        tire_Radius = self.tire_BaseRadius * self.Scale
        self.tireT_angZ_delta = (-1.0 * 360.0 * self.vel) / (2.0 * np.pi * tire_Radius)
        self.tireT_angZ = 0.0

        # Como se mueve el carro:
        #   'manual' -> lo maneja el usuario (modelo de bicicleta)
        #   'circle' -> da vueltas solo en un circulo (setCircle)
        #   'line'   -> va solo en linea recta y vuelve a empezar (setLine)
        self.mode = 'manual'

    def setCircle(self, center, radius, theta):
        # Circulo EXACTO de radio 'radius' alrededor de center = (x, z),
        # en sentido antihorario visto desde arriba. theta = angulo inicial
        # (radianes).
        self.mode = 'circle'
        self.center = center
        self.radius = radius
        self.theta = theta
        self.T1_F_ry = math.degrees(math.atan(self.L / radius))  # solo visual
        self.Moving = True
        self._placeOnCircle()

    def _placeOnCircle(self):
        th = self.theta
        self.pos[0] = self.center[0] + self.radius * math.sin(th)
        self.pos[2] = self.center[1] + self.radius * math.cos(th)
        # Tangente al circulo: Direction = (cos th, 0, -sin th)
        self.Body_ry = math.degrees(th) % 360.0
        self.Direction[0] = math.cos(th)
        self.Direction[2] = -math.sin(th)

    def setLine(self, start, end):
        # Va en linea recta de start a end = (x, z); al llegar vuelve a start
        self.mode = 'line'
        self.start = np.array([start[0], self.pos[1], start[1]])
        dx, dz = end[0] - start[0], end[1] - start[1]
        self.length = math.hypot(dx, dz)
        self.Body_ry = math.degrees(math.atan2(-dz, dx))  # viendo hacia end
        self.T1_F_ry = 0.0
        self.pos = self.start.copy()
        self.Moving = True

    def toggleMove(self):
        self.Moving = not self.Moving

    def setRotate(self, dir):
        # Gira solo las llantas frontales (direccion). Funciona aunque el
        # carro este quieto
        if dir == 'left':
            self.T1_F_ry = min(self.T1_F_ry + 5.0, self.MAX_STEER)
        elif dir == 'right':
            self.T1_F_ry = max(self.T1_F_ry - 5.0, -self.MAX_STEER)
        elif dir == 'center':
            self.T1_F_ry = 0.0

    def update(self):
        if not self.Moving:
            return

        # Las llantas solo ruedan cuando el carro avanza
        self.tireT_angZ = (self.tireT_angZ + self.tireT_angZ_delta) % 360.0

        if self.mode == 'circle':
            # Arco recorrido = vel  =>  d(theta) = vel / radius
            self.theta += self.vel / self.radius
            self._placeOnCircle()
            return

        # La carroceria gira segun el angulo de las llantas frontales
        # (modelo de bicicleta): d(theta) = vel / L * tan(delta)
        if self.T1_F_ry != 0.0:
            dtheta = (self.vel / self.L) * math.tan(math.radians(self.T1_F_ry))
            self.Body_ry = (self.Body_ry + math.degrees(dtheta)) % 360.0

        # La direccion sigue la rotacion de la carroceria.
        # glRotatef(Body_ry, 0, 1, 0) lleva el eje +X del modelo a (cos, 0, -sin)
        ang = math.radians(self.Body_ry)
        self.Direction[0] = math.cos(ang)
        self.Direction[2] = -math.sin(ang)

        # Se actualiza la posicion del carro
        self.pos += self.vel * self.Direction

        # En linea recta: al llegar al final, vuelve al inicio
        if self.mode == 'line' and np.linalg.norm(self.pos - self.start) >= self.length:
            self.pos = self.start.copy()

    def _drawRearTires(self, part, center):
        glPushMatrix()
        glTranslatef(center[0], center[1], center[2])  # 2. llevarla a su lugar
        glRotatef(self.tireT_angZ, 0.0, 0.0, 1.0)      # 1. rodar sobre su eje (Z)
        part.render()
        glPopMatrix()

    def _drawFrontTire(self, part, center):
        glPushMatrix()
        glTranslatef(center[0], center[1], center[2])  # 3. llevarla a su lugar
        glRotatef(self.T1_F_ry, 0.0, 1.0, 0.0)         # 2. direccion (eje Y vertical)
        glRotatef(self.tireT_angZ, 0.0, 0.0, 1.0)      # 1. rodar sobre su eje (Z)
        part.render()
        glPopMatrix()

    def draw(self):
        glPushMatrix()
        # Transformacion de todo el carro (afecta carroceria y llantas)
        glTranslatef(self.pos[0], self.pos[1], self.pos[2])  # 3. posicion en el mundo
        glRotatef(self.Body_ry, 0, 1, 0)                      # 2. orientacion
        glScalef(self.Scale, self.Scale, self.Scale)          # 1. tamano

        # Carroceria
        self.component[BODY].render()

        # Llantas traseras: solo ruedan
        self._drawRearTires(self.component[TIRES_BACK], self.tireT_pos)

        # Llantas frontales: ruedan + direccion
        self._drawFrontTire(self.component[TIRE_FL], self.tireFL_pos)
        self._drawFrontTire(self.component[TIRE_FR], self.tireFR_pos)

        glPopMatrix()

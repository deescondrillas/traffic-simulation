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

        # Centro de cada llanta en coordenadas del modelo (dentro de glScalef).
        # Los .obj de las llantas vienen centrados en el origen, por eso
        # hay que trasladarlos a su lugar.
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

        # Modo circulo exacto (None = manejo libre con el modelo de bicicleta)
        self.circle = None

    def setCircle(self, center, alpha, side='left'):
        # El origen del carro (pos) recorre un circulo EXACTO de radio alpha
        # alrededor de center = (x, z). La posicion se calcula directo desde
        # el angulo, asi que no se acumula error al integrar.
        # El carro se "pega" al circulo en el punto mas cercano a donde esta.
        s = 1.0 if side == 'left' else -1.0

        # Distancia del origen del modelo al eje trasero (escalada)
        d = -self.tireT_pos[0] * self.Scale
        if alpha <= d:
            raise ValueError(f"alpha debe ser mayor que {d:.1f}")

        # pos = C + s*alpha*(sin th, 0, cos th)  =>  th = atan2(s*dx, s*dz)
        dx = self.pos[0] - center[0]
        dz = self.pos[2] - center[1]
        theta = math.atan2(s * dx, s * dz)

        self.circle = {"cx": center[0], "cz": center[1],
                       "alpha": alpha, "s": s, "theta": theta}

        # Llantas frontales al angulo que corresponde a ese circulo.
        # El eje trasero va por dentro, a radio sqrt(alpha^2 - d^2).
        r_rear = math.sqrt(alpha * alpha - d * d)
        self.T1_F_ry = s * math.degrees(math.atan(self.L / r_rear))

        self._applyCircle()

    def clearCircle(self):
        self.circle = None
        self.T1_F_ry = 0.0

    def _applyCircle(self):
        c = self.circle
        th = c["theta"]
        # Posicion sobre el circulo
        self.pos[0] = c["cx"] + c["s"] * c["alpha"] * math.sin(th)
        self.pos[2] = c["cz"] + c["s"] * c["alpha"] * math.cos(th)
        # Orientacion tangente: Direction = (cos th, 0, -sin th)
        self.Body_ry = math.degrees(th) % 360.0
        self.Direction[0] = math.cos(th)
        self.Direction[2] = -math.sin(th)

    def toggleMove(self):
        self.Moving = not self.Moving

    def setRotate(self, dir):
        # Gira solo las llantas frontales (direccion). Funciona aunque el
        # carro este quieto: asi se puede planear el giro antes de avanzar.
        # La carroceria gira despues, en update(), al moverse.
        # Manejar a mano saca al carro del modo circulo.
        self.circle = None
        if dir == 'left':
            self.T1_F_ry = min(self.T1_F_ry + 5.0, self.MAX_STEER)
        elif dir == 'right':
            self.T1_F_ry = max(self.T1_F_ry - 5.0, -self.MAX_STEER)
        elif dir == 'center':
            self.T1_F_ry = 0.0

    def update(self):
        if not self.Moving:
            return

        if self.circle is not None:
            # Avanzar el angulo: arco recorrido = vel  =>  d(theta) = vel/alpha
            c = self.circle
            c["theta"] += c["s"] * self.vel / c["alpha"]
            self._applyCircle()
            self.tireT_angZ = (self.tireT_angZ + self.tireT_angZ_delta) % 360.0
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

        # Las llantas solo ruedan cuando el carro avanza
        self.tireT_angZ = (self.tireT_angZ + self.tireT_angZ_delta) % 360.0

    # OpenGL aplica las transformaciones al vertice en orden INVERSO al que
    # aparecen en el codigo: la ultima llamada antes de render() es la primera
    # que le pasa a la llanta. Como la llanta viene centrada en el origen,
    # cada rotacion ocurre sobre su propio centro y no hace falta trasladar
    # ida y vuelta a un pivote.

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

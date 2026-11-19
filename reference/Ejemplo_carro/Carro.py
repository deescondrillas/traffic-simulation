#Autor: Ivan Olmos Pineda

from pygame.locals import *
import pygame

# Cargamos las bibliotecas de OpenGL
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *

# Import obj loader
from objloader import *

import numpy as np
import random
import math

class Carro:
    
    def __init__(self, dim, vel, Scale):
        self.DimBoard = dim
        #Se inicializa una posicion en el tablero
        self.Position = np.array([0.0, 0.0, 0.0])
        #Se inicializa un vector de direccion
        self.Direction = np.array([1.0, 0.0, 0.0])
        #Se normaliza el vector de direccion
        m = math.sqrt(self.Direction[0]*self.Direction[0] + self.Direction[2]*self.Direction[2])
        self.Direction[0] /= m
        self.Direction[2] /= m
        #Se almacena la magnitud de velocidad
        self.vel = vel
        #arreglo de cubos
        self.component = []
        #Variables de control globales del carro
        self.Avanza = False
        self.Rota = False
        self.Scale = Scale
        self.Body_Ry = 0.0
        #rotacion de llantas frontales
        self.Ll_F_Ry = 0.0

        self.cos_ang = 0.0
        self.sin_ang = 0.0
        self.cos_angF = 0.0
        self.sin_angF = 0.0
        #Matrices para optimizacion de operadores
        # La siguiente declaracion asume que en tiempo de ejecucion se transpone la matriz
        # para usarla como la requiere OpenGL
        # self.M_Carroceria = np.identity(4, dtype=np.float32)
        # Para optimizar, se declaran las matrices identidad traspuestas
        self.M_Carroceria = np.identity(4, dtype=np.float32).T
        # Matriz para las llantas traseras
        self.M_Llantas_traseras = np.identity(4, dtype=np.float32).T
        # Matriz para la llanta frontal izquierda
        self.M_Llanta_F = np.identity(4, dtype=np.float32).T
        # Matriz para la llanta frontal derecha
        #self.M_Llanta_FR = np.identity(4, dtype=np.float32).T

        # Se define el radio base del objeto llanta (depende del tamaño del objeto grafico)
        # (se debe modificar manualmente dependiendo de dicho tamaño)
        self.Llanta_radio_base = 1.0
        # Radio de la llanta considerando la escala del carro
        self.Llanta_radio = self.Llanta_radio_base * self.Scale
        # Traslacion base del origen a la posicon del eje trasero del carro
        # Este vector depende de la escala del carro
        self.LlantaT_dist = self.Scale * np.array([-2.3,-0.5,0])
        self.LlantaT_pos = np.copy(self.LlantaT_dist)
        # Para que las llantas tengan el efecto de girar hacia adelante
        # se debe calcular el angulo de rotacion de las mismas a partir de la formula
        # theta = (360 * d) / (2*pi*r), donde d es la distancia a recorrer y r el 
        # radio de la llanta
        # La distancia a recorrer depende de la velocidad (el vector de direccion es unitario)
        # como se desea que el carrito avance, la rotación es en contra de las manecillas del reloj
        # con respecto al eje Z, por lo tanto es una rotación negativa
        self.LlantaT_angZ_delta = math.radians((-1.0 * 360.0 * self.vel) / (2.0 * np.pi * self.Llanta_radio))
        # angulo de rotacion inicial para las llantas frontales y traseras
        self.LlantaT_angZ = 0.0
        # variables para llantas frontales
        self.LlantaFL_pos = self.Scale * np.array([3.5, -0.5, -1.5])
        self.LlantaFR_pos = self.Scale * np.array([3.5, -0.5, 1.5])
        # Distancia entre ejes
        self.L = abs(self.LlantaFL_pos[0] - self.LlantaT_pos[0])
        # Intervalo de tiempo por frame
        self.dt = 100

    def getComponents(self, comp):
        self.component = comp
        
    def setAvanza(self):
        self.Avanza = True
        
    def setRota(self, dir):


        
    def update(self):
        if self.Avanza:
    
    # T_llanta: vector para ubicar la llanta en su posicion
    # id_llanta: para identificar si es llanta izquierda(1) o derecha(2)
    def llantaFrontal(self, T_llanta, id_llanta):
        # self.Ll_F_Ry
    
    def draw(self):
        glPushMatrix() #e0
        # Se define la maquina de estados
        # Se actualizan los componentes de la matriz optimizada
        self.cos_ang = math.cos(math.radians(self.Body_Ry))
        self.sin_ang = math.sin(math.radians(self.Body_Ry))

        glPopMatrix() # e0
        
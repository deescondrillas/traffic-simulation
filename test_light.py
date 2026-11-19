# A01739410 – Franco De Escondrillas
# A01739769 – Enrique Jiménez
# 2026-11-18

from sim.renderer import TrafficLightMesh, lit_lamp
from math import cos, radians, sin
from pygame.locals import *
from OpenGL.GLU import *
from OpenGL.GL import *
import pygame


SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
FOVY = 45.0
ZNEAR = 0.1
ZFAR = 200.0

# La cámara gira alrededor del centro del semáforo; arranca de frente (los focos miran hacia +Z)
TARGET = (4.0, 3.0, 0.0)
ORBIT_RADIUS = 18.0
ORBIT_STEP = 1.5 # grados por cuadro
HEIGHT_STEP = 0.15 # m por cuadro
GROUND_SIZE = 20.0

KEY_STATES = {K_1: "green", K_2: "blinking_green", K_3: "yellow", K_4: "red"}


def setup_gl() -> None:
  glClearColor(0.55, 0.62, 0.7, 1.0)
  glEnable(GL_DEPTH_TEST)
  glMatrixMode(GL_PROJECTION)
  glLoadIdentity()
  gluPerspective(FOVY, SCREEN_WIDTH / SCREEN_HEIGHT, ZNEAR, ZFAR)
  glMatrixMode(GL_MODELVIEW)
  glLightfv(GL_LIGHT0, GL_AMBIENT, (0.5, 0.5, 0.5, 1.0))
  glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.5, 0.5, 0.5, 1.0))
  glEnable(GL_LIGHTING)
  glEnable(GL_LIGHT0)
  glEnable(GL_COLOR_MATERIAL)


def draw_ground() -> None:
  glColor3f(0.3, 0.3, 0.32)
  glNormal3f(0.0, 1.0, 0.0)
  glBegin(GL_QUADS)
  glVertex3f(-GROUND_SIZE, 0.0, -GROUND_SIZE)
  glVertex3f(-GROUND_SIZE, 0.0, GROUND_SIZE)
  glVertex3f(GROUND_SIZE, 0.0, GROUND_SIZE)
  glVertex3f(GROUND_SIZE, 0.0, -GROUND_SIZE)
  glEnd()


def main() -> None:
  pygame.init()
  pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DOUBLEBUF | OPENGL)
  setup_gl()
  mesh = TrafficLightMesh()
  clock = pygame.time.Clock()

  state = "red"
  state_start = pygame.time.get_ticks()
  angle = 0.0
  eye_y = TARGET[1]
  done = False
  while not done:
    for event in pygame.event.get():
      if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
        done = True
      elif event.type == KEYDOWN and event.key in KEY_STATES:
        state = KEY_STATES[event.key]
        state_start = pygame.time.get_ticks()
    keys = pygame.key.get_pressed()
    angle += ORBIT_STEP * (keys[K_RIGHT] - keys[K_LEFT])
    eye_y += HEIGHT_STEP * (keys[K_UP] - keys[K_DOWN])
    pygame.display.set_caption(f"Semáforo: {state} (1 verde, 2 verde parpadeante, 3 amarillo, 4 rojo)")

    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    eye_x = TARGET[0] + ORBIT_RADIUS * sin(radians(angle))
    eye_z = TARGET[2] + ORBIT_RADIUS * cos(radians(angle))
    gluLookAt(eye_x, eye_y, eye_z, *TARGET, 0.0, 1.0, 0.0)
    # La luz se fija después de la cámara para que quede en coordenadas del mundo
    glLightfv(GL_LIGHT0, GL_POSITION, (0.5, 1.0, 1.0, 0.0))
    draw_ground()
    mesh.draw(lit_lamp(state, (pygame.time.get_ticks() - state_start) / 1000))
    pygame.display.flip()
    clock.tick(60)

  mesh.free()
  pygame.quit()


if __name__ == "__main__":
  main()

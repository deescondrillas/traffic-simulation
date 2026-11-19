# A01739410 – Franco De Escondrillas
# A01739769 – Enrique Jiménez
# 2026-11-18

from sim.config import FPS, SCREEN_HEIGHT, SCREEN_WIDTH, SIM_DT
from sim.renderer import CityRenderer, OrbitCamera, setup_gl
from sim.city_model import CityModel
from pygame.locals import *
from OpenGL.GL import *
import pygame


def main() -> None:
  pygame.init()
  pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DOUBLEBUF | OPENGL)
  pygame.display.set_caption("Étoile: flechas para mover la cámara, Esc para salir")
  setup_gl()
  model = CityModel({"seed": 1})
  model.sim_setup()
  renderer = CityRenderer()
  camera = OrbitCamera()
  clock = pygame.time.Clock()

  acc = 0.0
  done = False
  while not done:
    for event in pygame.event.get():
      if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
        done = True
    keys = pygame.key.get_pressed()
    camera.update(keys[K_RIGHT] - keys[K_LEFT], keys[K_UP] - keys[K_DOWN])

    # Simulación a paso fijo, independiente de los FPS
    acc += clock.get_time() / 1000
    while acc >= SIM_DT:
      model.sim_step()
      acc -= SIM_DT

    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    camera.apply()
    renderer.draw(model)
    pygame.display.flip()
    clock.tick(FPS)

  renderer.free()
  pygame.quit()


if __name__ == "__main__":
  main()

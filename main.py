#  Franco De Escondrillas ft. Claude Code · 2026-11-26
"""Simulación en vivo: el ciclo de pygame avanza el modelo a paso fijo y el renderizador solo lo lee.

Antes, `train.ipynb` guarda a los conductores con curso de manejo; sin ese archivo salen novatos.
"""

import pygame
from OpenGL.GL import *
from pygame.locals import *

from config import (
  DRIVERS_FILE, FPS, N_CARS, SCREEN_HEIGHT, SCREEN_WIDTH, SEED, SIM_DT,
)
from environment.city_model import CityModel
from visual.renderer import CityRenderer, OrbitCamera, setup_gl

CAPTION_EVERY = 30  # cuadros entre actualizaciones del título de la ventana


def main() -> None:
  pygame.init()
  pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DOUBLEBUF | OPENGL)
  setup_gl()
  model = CityModel({"n_cars": N_CARS, "seed": SEED, "drivers": DRIVERS_FILE})
  model.sim_setup()
  drivers = "con curso de manejo" if model.trained else "novatos (corre train.ipynb)"
  renderer = CityRenderer()
  camera = OrbitCamera()
  clock = pygame.time.Clock()

  acc = 0.0
  frame = 0
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

    frame += 1
    if frame % CAPTION_EVERY == 0:
      pygame.display.set_caption(
        f"Étoile · {len(model.cars)} coches {drivers} · t = {model.time:5.0f} s · "
        f"{clock.get_fps():3.0f} FPS · flechas: cámara, Esc: salir")

  renderer.free()
  pygame.quit()


if __name__ == "__main__":
  main()

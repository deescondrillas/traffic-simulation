# A01739410 – Franco De Escondrillas
# A01739769 – Enrique Jiménez
# 2026-11-30

from config import DRIVERS_FILE, FPS, N_CARS, SCREEN_HEIGHT, SCREEN_WIDTH, SEED, SIM_DT
from visual.renderer import CityRenderer, OrbitCamera, setup_gl
from environment.city_model import CityModel
from pygame.locals import *
from OpenGL.GL import *
import pygame

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
      elif event.type == KEYDOWN and event.key == K_SPACE:
        camera.auto_orbit = not camera.auto_orbit
    keys = pygame.key.get_pressed()
    camera.update(keys[K_RIGHT] - keys[K_LEFT], keys[K_UP] - keys[K_DOWN], keys[K_w] - keys[K_s])

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
        f"{clock.get_fps():3.0f} FPS · flechas: girar, W/S: zoom, espacio: auto-giro, Esc: salir")

  renderer.free()
  pygame.quit()


if __name__ == "__main__":
  main()

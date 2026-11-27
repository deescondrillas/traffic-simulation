#  Franco De Escondrillas ft. Claude Code · 2026-11-26

import colorsys
import os
from math import cos, degrees, radians, sin, tau
import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.arrays import vbo

from config import (
  AUTO_ORBIT_STEP,
  BLINKER_COLOR,
  BLINKER_PERIOD,
  BRAKE_COLOR,
  CAR_DIR,
  CAR_HUES,
  CAR_LAMP_SIZE,
  CAR_PARTS,
  CAR_SCALE,
  FRONT_LAMP,
  FRONT_TIRE,
  REAR_AXLE,
  ROAD_Y,
  TAIL_LAMP,
  TIRE_RADIUS,
  CAMERA_MIN_HEIGHT,
  CAMERA_ORBIT_RADIUS,
  CAMERA_START_HEIGHT,
  CAMERA_TARGET,
  CLEAR_COLOR,
  FOVY,
  GREEN_BLINK_PERIOD,
  HEIGHT_STEP,
  LAMP_COLOR_TOLERANCE,
  LAMP_HALO_ALPHA,
  LAMP_HALO_OFFSET,
  LAMP_HALO_SCALE,
  LAMP_HALO_SEGMENTS,
  LAMP_MESH_COLORS,
  LAMP_OFF_FACTOR,
  LAMP_ON_COLORS,
  MAP_OBJ,
  ORBIT_STEP,
  SCREEN_HEIGHT,
  SCREEN_WIDTH,
  TRAFFIC_LIGHT_HEIGHT,
  TRAFFIC_LIGHT_OBJ,
  ZFAR,
  ZNEAR,
)
from agents.car_agent import STOPPED, YIELDING
from visual.objloader import OBJ

Vec3 = tuple[float, float, float]
Vertex = tuple[Vec3, Vec3, Vec3] # posición, normal, color
Triangle = tuple[Vertex, Vertex, Vertex]


class _MeshData(OBJ):
  """Solo lee el archivo: las display lists se arman aparte, una por pieza."""

  generate_on_init = False


def _read_vertex_color_obj(path: str) -> list[tuple[list[int], list[Triangle]]]:
  """Lee un OBJ con color por vértice (`v x y z r g b`) y lo regresa en triángulos.

  Cada triángulo va junto con los índices de sus vértices, para poder separar
  después las piezas conexas.
  """
  obj = _MeshData(path)
  positions, normals = _to_map_frame(obj.vertices, obj.normals)
  triangles = []
  for face, norms, _, _ in obj.faces:
    corners = [(v - 1, n - 1 if n > 0 else None) for v, n in zip(face, norms)]
    # Abanico: el OBJ ya viene en triángulos, pero así también acepta polígonos
    for k in range(1, len(corners) - 1):
      tri = (corners[0], corners[k], corners[k + 1])
      triangles.append((
        [v for v, _ in tri],
        tuple((positions[v], normals[n] if n is not None else (0.0, 0.0, 1.0), obj.colors[v]) for v, n in tri),
      ))
  return triangles


def _to_map_frame(positions: list[Vec3], normals: list[Vec3]) -> tuple[list[Vec3], list[Vec3]]:
  """Pasa del marco exportado (poste hacia +Z, focos hacia −Y) al del mapa.

  Queda la base del poste en el origen, Y hacia arriba, brazo hacia +X y focos
  mirando hacia +Z, con la altura del poste en metros.
  """
  low = min(p[2] for p in positions)
  high = max(p[2] for p in positions)
  base = [p for p in positions if p[2] == low]
  x0 = sum(p[0] for p in base) / len(base)
  y0 = sum(p[1] for p in base) / len(base)
  s = TRAFFIC_LIGHT_HEIGHT / (high - low)
  positions = [((x - x0) * s, (z - low) * s, -(y - y0) * s) for x, y, z in positions]
  normals = [(x, z, -y) for x, y, z in normals]
  return positions, normals


def _lamp_of(color: Vec3) -> str | None:
  for name, lamp_color in LAMP_MESH_COLORS.items():
    if max(abs(a - b) for a, b in zip(color, lamp_color)) < LAMP_COLOR_TOLERANCE:
      return name
  return None


def _connected_pieces(triangles: list[tuple[list[int], Triangle]]) -> list[list[Triangle]]:
  """Separa los triángulos en piezas conexas (un foco por cabeza del semáforo)."""
  parent = {}

  def find(a):
    while parent.setdefault(a, a) != a:
      parent[a] = parent[parent[a]]
      a = parent[a]
    return a

  for ids, _ in triangles:
    for v in ids[1:]:
      parent[find(v)] = find(ids[0])
  pieces = {}
  for ids, tri in triangles:
    pieces.setdefault(find(ids[0]), []).append(tri)
  return list(pieces.values())


class _Mesh:
  """Triángulos en un VBO intercalado: posición, normal y, si `with_color`, color.

  Con 60 coches y 34 semáforos, las display lists de PyOpenGL en macOS no llegan a 30 FPS;
  el VBO dibuja lo mismo ≈ 2.4 veces más rápido.
  """

  def __init__(self, triangles: list[Triangle], with_color: bool) -> None:
    rows = [(*p, *n, *c) if with_color else (*p, *n) for tri in triangles for p, n, c in tri]
    self._with_color = with_color
    self._stride = (9 if with_color else 6) * 4  # bytes por vértice (float32)
    self._count = len(rows)
    self._buffer = vbo.VBO(np.array(rows, dtype=np.float32))

  def draw(self) -> None:
    self._buffer.bind()
    glEnableClientState(GL_VERTEX_ARRAY)
    glEnableClientState(GL_NORMAL_ARRAY)
    glVertexPointer(3, GL_FLOAT, self._stride, self._buffer)
    glNormalPointer(GL_FLOAT, self._stride, self._buffer + 12)
    if self._with_color:
      glEnableClientState(GL_COLOR_ARRAY)
      glColorPointer(3, GL_FLOAT, self._stride, self._buffer + 24)
    glDrawArrays(GL_TRIANGLES, 0, self._count)
    glDisableClientState(GL_COLOR_ARRAY)
    glDisableClientState(GL_NORMAL_ARRAY)
    glDisableClientState(GL_VERTEX_ARRAY)
    self._buffer.unbind()

  def free(self) -> None:
    self._buffer.delete()


def _read_material_obj(path: str, swapyz: bool) -> list[Triangle]:
  """Lee un OBJ con `.mtl` y lo regresa en triángulos con el color difuso de su material."""
  obj = _MeshData(path, swapyz=swapyz)
  triangles = []
  for face, norms, _, material in obj.faces:
    color = tuple(obj.mtl[material]["Kd"][:3]) if material in obj.mtl else (1.0, 1.0, 1.0)
    corners = [(obj.vertices[v - 1], obj.normals[n - 1] if n > 0 else (0.0, 1.0, 0.0), color)
               for v, n in zip(face, norms)]
    for k in range(1, len(corners) - 1):
      triangles.append((corners[0], corners[k], corners[k + 1]))
  return triangles


def shift_hue(color: Vec3, shift: float) -> Vec3:
  """Gira el tono de `color` `shift` vueltas (0..1) en HSV; los grises y el negro no cambian."""
  h, s, v = colorsys.rgb_to_hsv(*color)
  return colorsys.hsv_to_rgb((h + shift) % 1.0, s, v)


def _compile_halos(pieces: list[list[Triangle]], color: Vec3, front_z: float) -> int:
  """Un disco degradado, transparente hacia la orilla, delante de cada foco."""
  gl_list = glGenLists(1)
  glNewList(gl_list, GL_COMPILE)
  for piece in pieces:
    xs = [p[0] for tri in piece for p, _, _ in tri]
    ys = [p[1] for tri in piece for p, _, _ in tri]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    r = (max(xs) - min(xs)) / 2 * LAMP_HALO_SCALE
    z = front_z + LAMP_HALO_OFFSET
    glBegin(GL_TRIANGLE_FAN)
    glColor4f(*color, LAMP_HALO_ALPHA)
    glVertex3f(cx, cy, z)
    glColor4f(*color, 0.0)
    for k in range(LAMP_HALO_SEGMENTS + 1):
      a = tau * k / LAMP_HALO_SEGMENTS
      glVertex3f(cx + r * cos(a), cy + r * sin(a), z)
    glEnd()
  glEndList()
  return gl_list


class TrafficLightMesh:
  """Semáforo de `assets/traffic_light/traffic_light.obj` con focos que se encienden por código.

  El OBJ no trae `.mtl`, pero sí color por vértice: cada foco se reconoce por el
  color con que se exportó (`LAMP_MESH_COLORS`). El cuerpo y cada color de foco se
  compilan en display lists separadas, así un solo modelo sirve para los 11
  semáforos en cualquier estado.

  Requiere `GL_COLOR_MATERIAL` activo si hay iluminación, igual que el ejemplo de clase.
  """

  def __init__(self, path: str = TRAFFIC_LIGHT_OBJ) -> None:
    triangles = _read_vertex_color_obj(path)
    front_z = max(p[2] for _, tri in triangles for p, _, _ in tri)
    body = []
    lamps = {name: [] for name in LAMP_MESH_COLORS}
    for ids, tri in triangles:
      name = _lamp_of(tri[0][2])
      (lamps[name] if name else body).append((ids, tri))

    self._body = _Mesh([tri for _, tri in body], with_color=True)
    self._lamps = {name: _Mesh([tri for _, tri in tris], with_color=False) for name, tris in lamps.items()}
    self._halos = {
      name: _compile_halos(_connected_pieces(tris), LAMP_ON_COLORS[name], front_z)
      for name, tris in lamps.items()
    }

  def draw(self, lit: str | None = None) -> None:
    """Dibuja el semáforo con el foco `lit` ("red", "yellow" o "green") encendido."""
    self._body.draw()
    for name, mesh in self._lamps.items():
      if name != lit:
        glColor3f(*(c * LAMP_OFF_FACTOR for c in LAMP_MESH_COLORS[name]))
        mesh.draw()
    if lit is None:
      return

    glPushAttrib(GL_ENABLE_BIT | GL_CURRENT_BIT | GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    # Sin iluminación el foco sale a color pleno desde cualquier ángulo: parece emitir luz
    glDisable(GL_LIGHTING)
    glDisable(GL_TEXTURE_2D)
    glColor3f(*LAMP_ON_COLORS[lit])
    self._lamps[lit].draw()
    # Mezcla aditiva para el resplandor; sin escribir profundidad para no tapar lo de atrás
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE)
    glDepthMask(GL_FALSE)
    glCallList(self._halos[lit])
    glPopAttrib()

  def free(self) -> None:
    self._body.free()
    for mesh in self._lamps.values():
      mesh.free()
    for gl_list in self._halos.values():
      glDeleteLists(gl_list, 1)


def lit_lamp(state: str, seconds_in_state: float) -> str | None:
  """Foco encendido para un estado del semáforo; el verde parpadeante alterna con apagado."""
  if state == "blinking_green":
    return "green" if int(seconds_in_state / GREEN_BLINK_PERIOD) % 2 == 0 else None
  return state


def setup_gl(zfar: float = ZFAR) -> None:
  glClearColor(*CLEAR_COLOR)
  glEnable(GL_DEPTH_TEST)
  glMatrixMode(GL_PROJECTION)
  glLoadIdentity()
  gluPerspective(FOVY, SCREEN_WIDTH / SCREEN_HEIGHT, ZNEAR, zfar)
  glMatrixMode(GL_MODELVIEW)
  glLightfv(GL_LIGHT0, GL_AMBIENT, (0.5, 0.5, 0.5, 1.0))
  glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.5, 0.5, 0.5, 1.0))
  glEnable(GL_LIGHTING)
  glEnable(GL_LIGHT0)
  glEnable(GL_COLOR_MATERIAL)
  glEnable(GL_NORMALIZE) # los coches usan glScalef; sin esto la luz falla


class OrbitCamera:
  """Cámara que gira sola alrededor de `target` mirándolo siempre; solo cambia ángulo y altura."""

  def __init__(
    self,
    target: Vec3 = CAMERA_TARGET,
    radius: float = CAMERA_ORBIT_RADIUS,
    height: float = CAMERA_START_HEIGHT,
  ) -> None:
    self.target = target
    self.radius = radius
    self.height = height
    self.angle = 0.0 # grados

  def update(self, turn: int, climb: int, orbit_step: float = ORBIT_STEP, height_step: float = HEIGHT_STEP) -> None:
    """`turn` y `climb` valen −1, 0 o 1 según las flechas presionadas."""
    self.angle += orbit_step * turn + AUTO_ORBIT_STEP
    self.height = max(CAMERA_MIN_HEIGHT, self.height + height_step * climb)

  def apply(self) -> None:
    glLoadIdentity()
    eye_x = self.target[0] + self.radius * sin(radians(self.angle))
    eye_z = self.target[2] + self.radius * cos(radians(self.angle))
    gluLookAt(eye_x, self.height, eye_z, *self.target, 0.0, 1.0, 0.0)
    # La luz se fija después de la cámara para que quede en coordenadas del mundo
    glLightfv(GL_LIGHT0, GL_POSITION, (0.5, 1.0, 1.0, 0.0))


def _compile_by_material(path: str, swapyz: bool = False) -> int:
  """Display list de un OBJ con un solo `glBegin` por material.

  `OBJ.generate` abre un `GL_POLYGON` por cara; con las ~100 000 caras del mapa eso
  baja a menos de 10 FPS.
  """
  obj = _MeshData(path, swapyz=swapyz)
  by_material = {}
  for face, norms, _, material in obj.faces:
    for k in range(1, len(face) - 1):
      by_material.setdefault(material, []).extend(
        (face[i] - 1, norms[i] - 1 if norms[i] > 0 else None) for i in (0, k, k + 1)
      )
  gl_list = glGenLists(1)
  glNewList(gl_list, GL_COMPILE)
  for material, corners in by_material.items():
    glColor3fv(obj.mtl[material]["Kd"] if material in obj.mtl else (1.0, 1.0, 1.0))
    glBegin(GL_TRIANGLES)
    for v, n in corners:
      if n is not None:
        glNormal3fv(obj.normals[n])
      glVertex3fv(obj.vertices[v])
    glEnd()
  glEndList()
  return gl_list


class CarMesh:
  """Coche en piezas (`assets/car`), dibujado como en `Carro.py`: carrocería, llantas traseras
  que ruedan y delanteras que además giran con la dirección. Las luces de freno y las
  direccionales son cuadros sin iluminación, para que parezcan encendidas.
  """

  def __init__(self) -> None:
    body, *wheels = (_read_material_obj(os.path.join(CAR_DIR, part), swapyz=True) for part in CAR_PARTS)
    self._front_left, self._front_right, self._rear = (_Mesh(tris, with_color=True) for tris in wheels)
    self._body_triangles = body
    self._bodies: dict[int, _Mesh] = {} # una carrocería por tono, creada la primera vez que se pide
    self._lift = (TIRE_RADIUS - REAR_AXLE[1]) * CAR_SCALE # del origen del modelo al piso, en m

  def draw(self, car, time: float) -> None:
    x, z, psi, steer = car.render_pose()
    spin = -degrees(car.odometer / (TIRE_RADIUS * CAR_SCALE)) # negativo: ruedan hacia adelante
    glPushMatrix()
    glTranslatef(x, ROAD_Y + self._lift, z)
    glRotatef(degrees(psi), 0.0, 1.0, 0.0)
    glScalef(CAR_SCALE, CAR_SCALE, CAR_SCALE)
    self._body(car.hue).draw()
    self._wheel(self._rear, REAR_AXLE, 0.0, spin)
    self._wheel(self._front_left, FRONT_TIRE, steer, spin)
    self._wheel(self._front_right, (FRONT_TIRE[0], FRONT_TIRE[1], -FRONT_TIRE[2]), steer, spin)
    self._lamps(car, time)
    glPopMatrix()

  def _body(self, hue: float) -> _Mesh:
    """Carrocería con el tono más cercano a `hue` de los `CAR_HUES` posibles."""
    step = round(hue * CAR_HUES) % CAR_HUES
    if step not in self._bodies:
      shift = step / CAR_HUES
      self._bodies[step] = _Mesh(
        [tuple((p, n, shift_hue(c, shift)) for p, n, c in tri) for tri in self._body_triangles], with_color=True
      )
    return self._bodies[step]

  @staticmethod
  def _wheel(mesh: _Mesh, center: Vec3, steer: float, spin: float) -> None:
    glPushMatrix()
    glTranslatef(*center)
    glRotatef(degrees(steer), 0.0, 1.0, 0.0) # dirección (eje vertical)
    glRotatef(spin, 0.0, 0.0, 1.0)           # rodar sobre su eje
    mesh.draw()
    glPopMatrix()

  @staticmethod
  def _lamps(car, time: float) -> None:
    lamps = []
    if car.state in (YIELDING, STOPPED):
      lamps += [(TAIL_LAMP, side, BRAKE_COLOR) for side in (1, -1)]
    if car.change_timer > 0 and int(time / BLINKER_PERIOD) % 2 == 0:
      # Hacia dentro de la Étoile (índice mayor) es a la izquierda: −Z en el modelo
      side = -1 if int(car.lane_id[-1]) > int(car.prev_lane[-1]) else 1
      lamps += [(TAIL_LAMP, side, BLINKER_COLOR), (FRONT_LAMP, side, BLINKER_COLOR)]
    if not lamps:
      return
    glPushAttrib(GL_ENABLE_BIT | GL_CURRENT_BIT)
    glDisable(GL_LIGHTING)
    glDisable(GL_TEXTURE_2D)
    glBegin(GL_QUADS)
    for (lx, ly, lz), side, color in lamps:
      glColor3f(*color)
      cz = lz * side
      for dy, dz in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
        glVertex3f(lx, ly + dy * CAR_LAMP_SIZE, cz + dz * CAR_LAMP_SIZE)
    glEnd()
    glPopAttrib()

  def free(self) -> None:
    for mesh in (*self._bodies.values(), self._front_left, self._front_right, self._rear):
      mesh.free()


class CityRenderer:
  """Dibuja el mapa, los semáforos y los coches de un `CityModel`, sin modificarlo."""

  def __init__(self) -> None:
    self._map = _compile_by_material(MAP_OBJ)
    self._light = TrafficLightMesh()
    self._car = CarMesh()

  def draw(self, model) -> None:
    glCallList(self._map)
    for light in model.light_heads:
      glPushMatrix()
      glTranslatef(light.x, 0.0, light.z)
      glRotatef(degrees(light.yaw), 0.0, 1.0, 0.0)
      # Espejo: el brazo del modelo apunta a la derecha del conductor y el poste va en la esquina derecha
      glScalef(-1.0, 1.0, 1.0)
      self._light.draw(lit_lamp(light.state, light.state_time))
      glPopMatrix()
    for car in model.cars:
      self._car.draw(car, model.time)

  def free(self) -> None:
    glDeleteLists(self._map, 1)
    self._light.free()
    self._car.free()

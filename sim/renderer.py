# A01739410 – Franco De Escondrillas
# A01739769 – Enrique Jiménez
# 2026-11-18

from math import cos, degrees, radians, sin, tau
from OpenGL.GL import *
from OpenGL.GLU import *

from sim.config import (
  AUTO_ORBIT_STEP,
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
from sim.objloader import OBJ

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


def _compile(triangles: list[Triangle], with_color: bool) -> int:
  gl_list = glGenLists(1)
  glNewList(gl_list, GL_COMPILE)
  glBegin(GL_TRIANGLES)
  for tri in triangles:
    for position, normal, color in tri:
      if with_color:
        glColor3fv(color)
      glNormal3fv(normal)
      glVertex3fv(position)
  glEnd()
  glEndList()
  return gl_list


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
  """Semáforo de `assets/traffic_light.obj` con focos que se encienden por código.

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

    self._body = _compile([tri for _, tri in body], with_color=True)
    self._lamps = {name: _compile([tri for _, tri in tris], with_color=False) for name, tris in lamps.items()}
    self._halos = {
      name: _compile_halos(_connected_pieces(tris), LAMP_ON_COLORS[name], front_z)
      for name, tris in lamps.items()
    }

  def draw(self, lit: str | None = None) -> None:
    """Dibuja el semáforo con el foco `lit` ("red", "yellow" o "green") encendido."""
    glCallList(self._body)
    for name, gl_list in self._lamps.items():
      if name != lit:
        glColor3f(*(c * LAMP_OFF_FACTOR for c in LAMP_MESH_COLORS[name]))
        glCallList(gl_list)
    if lit is None:
      return

    glPushAttrib(GL_ENABLE_BIT | GL_CURRENT_BIT | GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    # Sin iluminación el foco sale a color pleno desde cualquier ángulo: parece emitir luz
    glDisable(GL_LIGHTING)
    glDisable(GL_TEXTURE_2D)
    glColor3f(*LAMP_ON_COLORS[lit])
    glCallList(self._lamps[lit])
    # Mezcla aditiva para el resplandor; sin escribir profundidad para no tapar lo de atrás
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE)
    glDepthMask(GL_FALSE)
    glCallList(self._halos[lit])
    glPopAttrib()

  def free(self) -> None:
    glDeleteLists(self._body, 1)
    for gl_list in [*self._lamps.values(), *self._halos.values()]:
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


def _compile_map(path: str) -> int:
  """Display list del mapa con un solo `glBegin` por material.

  `OBJ.generate` abre un `GL_POLYGON` por cara; con las ~100 000 caras del mapa eso
  baja a menos de 10 FPS.
  """
  obj = _MeshData(path)
  by_material = {}
  for face, norms, _, material in obj.faces:
    for k in range(1, len(face) - 1):
      by_material.setdefault(material, []).extend(
        (face[i] - 1, norms[i] - 1 if norms[i] > 0 else None) for i in (0, k, k + 1)
      )
  gl_list = glGenLists(1)
  glNewList(gl_list, GL_COMPILE)
  for material, corners in by_material.items():
    glColor3fv(obj.mtl[material]["Kd"])
    glBegin(GL_TRIANGLES)
    for v, n in corners:
      if n is not None:
        glNormal3fv(obj.normals[n])
      glVertex3fv(obj.vertices[v])
    glEnd()
  glEndList()
  return gl_list


class CityRenderer:
  """Dibuja el mapa y los semáforos de un `CityModel`, sin modificarlo."""

  def __init__(self) -> None:
    self._map = _compile_map(MAP_OBJ)
    self._light = TrafficLightMesh()

  def draw(self, model) -> None:
    glCallList(self._map)
    for light in model.lights:
      glPushMatrix()
      glTranslatef(light.x, 0.0, light.z)
      glRotatef(degrees(light.yaw), 0.0, 1.0, 0.0)
      # Espejo: el brazo del modelo apunta a la derecha del conductor y el poste va en la esquina derecha
      glScalef(-1.0, 1.0, 1.0)
      self._light.draw(lit_lamp(light.state, light.state_time))
      glPopMatrix()

  def free(self) -> None:
    glDeleteLists(self._map, 1)
    self._light.free()

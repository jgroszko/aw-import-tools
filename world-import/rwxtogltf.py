import sys, os.path
import pygltflib, numpy as np
from functools import reduce

class RwxToGltf():
  """
  Converts parsed RWX models to GLTF
  """

  def __init__(self, rwx):
    self.rwx = rwx

    self.buffer = b''
    self.bufferViews = []
    self.accessors = []
    self.materials = []
    self.material_dicts = []
    self.meshes = []
    self.nodes = []

    self.root_node = self.convert(self.rwx)

  def save(self, filename):
    gltf = pygltflib.GLTF2(
      scene=0,
      scenes=[pygltflib.Scene(nodes=[self.root_node])],
      nodes=self.nodes,
      materials=self.materials,
      meshes=self.meshes,
      buffers=[pygltflib.Buffer(byteLength=len(self.buffer))],
      bufferViews=self.bufferViews,
      accessors=self.accessors
    )
    gltf.set_binary_blob(self.buffer)
    gltf.convert_buffers(pygltflib.BufferFormat.DATAURI)
    gltf.save_json(filename)

  def add_to_buffer(self, data):
    offset = len(self.buffer)

    length = len(data)

    self.buffer += data

    # Make sure we stay aligned to 4 bytes
    if(length % 4 != 0):
      self.buffer += b'0' * (4 - (length % 4))

    return (offset, length)

  def add_to_material(self, materials):
    material = {
      "r": 0.5,
      "g": 0.5,
      "b": 0.5,
      "a": 1.0,
      "metallic": 1.0,
      "roughness": 0.0
    }
    for m in materials:
      if(m['type'] == 'color'):
        material['r'] = m['r']
        material['g'] = m['g']
        material['b'] = m['b']
      elif(m['type'] == "surface"):
        # Quick and dirty conversion...
        material['metallic'] = m['diffuse']
        material['roughness'] = m['specular']
      elif(m['type'] == "opacity"):
        material['a'] = m['opacity']
      elif(m['type'] == "texture"):
        material['texture'] = m['texture']

    # See if material exists already
    for (i, m) in enumerate(self.material_dicts):
      if material == m:
        return i

    # Create new one
    result = len(self.materials)
    self.material_dicts.append(material)
    self.materials.append(pygltflib.Material(
      pbrMetallicRoughness={
        "baseColorFactor": [material['r'], material['g'], material['b'], material['a']],
        "metallicFactor": material['metallic'],
        "roughnessFactor": material['roughness'],
      },
      alphaCutoff=None
    ))
    return result

  def convert(self, rwx):
    node_index = len(self.nodes)
    node = pygltflib.Node()
    self.nodes.append(node)

    if 'transforms' in rwx and len(rwx['transforms']) > 0:
      for transform in rwx['transforms']:
        if(transform['type'] == "transform"):
          node.matrix = transform['matrix']

    if 'vertices' in rwx and 'triangles' in rwx and len(rwx['vertices']) > 0 and len(['triangles']) > 0:
      vertex_data = np.array([[v['x'], v['y'], v['z']] for v in rwx['vertices']], dtype="float32")
      
      points_accessor = len(self.accessors)
      self.accessors.append(pygltflib.Accessor(
        bufferView=len(self.bufferViews),
        componentType=pygltflib.FLOAT,
        count=len(vertex_data),
        type=pygltflib.VEC3,
        max=vertex_data.max(axis=0).tolist(),
        min=vertex_data.min(axis=0).tolist()
      ))

      (vertex_offset, vertex_length) = self.add_to_buffer(vertex_data.flatten().tobytes())
      self.bufferViews.append(pygltflib.BufferView(
        buffer=0,
        byteOffset=vertex_offset,
        byteLength=vertex_length,
        target=pygltflib.ARRAY_BUFFER
      ))
      
      grouped_triangles = {}
      for triangle in rwx['triangles']:
        if triangle['material'] in grouped_triangles:
          grouped_triangles[triangle['material']].append(triangle['indices'])
        else:
          grouped_triangles[triangle['material']] = [triangle['indices']]

      primitives = []
      for (material, triangles) in grouped_triangles.items():
        short_indices = np.array(triangles).flatten().max() < 255
        index_data = np.array(triangles, dtype="uint8" if short_indices else "uint16")-1

        index_accessor = len(self.accessors)
        self.accessors.append(pygltflib.Accessor(
          bufferView=len(self.bufferViews),
          componentType=pygltflib.UNSIGNED_BYTE if short_indices else pygltflib.UNSIGNED_SHORT,
          count=len(index_data.flatten()),
          type=pygltflib.SCALAR,
          min=[int(index_data.min())],
          max=[int(index_data.max())]
        ))

        (index_offset, index_length) = self.add_to_buffer(index_data.flatten().tobytes())
        self.bufferViews.append(pygltflib.BufferView(
          buffer=0,
          byteOffset=index_offset,
          byteLength=index_length,
          target=pygltflib.ELEMENT_ARRAY_BUFFER
        ))

        material = self.add_to_material(rwx['materials'][0:material])

        primitives.append(pygltflib.Primitive(
          attributes=pygltflib.Attributes(POSITION=points_accessor), indices=index_accessor, material=material
        ))

      mesh = len(self.meshes)
      self.meshes.append(pygltflib.Mesh(primitives=primitives))

      node.mesh = mesh

    if 'children' in rwx and len(rwx['children']) > 0:
      for child in rwx['children']:
        node.children.append(self.convert(child['clump']))

    return node_index

if __name__ == "__main__":
  from rwxreader import RwxReader

  filename = '00PS.RWX'
  if len(sys.argv) > 1:
    filename = sys.argv[1]

  with open(filename) as f:
    rwx = RwxReader(f)
    gltf = RwxToGltf(rwx.model)
    gltf.save(os.path.splitext(filename)[0] + '.gltf')

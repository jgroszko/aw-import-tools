import json
import math, numpy

TEXTURE_FILE_FORMAT = "%s.png"

class RwxToThree():
    """
    Converts parsed RWX models to Three.js format
    """

    def __init__(self, rwx):
        self.rwx = rwx

        self.model = {
            'vertices': [],
            'uvs': [[],],
            'normals': [],
            'faces': [],
            'materials': [],
        }

        self.convert(rwx)

    def write_json(self, filename, compact=False):
        dump_options = ({
            'separators': (',',':')
        } if compact
        else {
                'indent': 4
        })

        with open(filename, 'w') as outfile:
            json.dump(
                self.model,
                outfile,
                **dump_options)

    def convert_material(self, material):
        new_material = {
            "colorAmbient": [c*material['ambient'] for c in material['color']],
            "colorDiffuse": [c*material['diffuse'] for c in material['color']],
            "colorSpecular": [material['specular'], material['specular'], material['specular']],
        }

        if('texture' in material):
            if(material['texture'] is None):
                new_material['mapDiffuse'] = None
            else:
                new_material['mapDiffuse'] = TEXTURE_FILE_FORMAT % material['texture']

        return new_material

    def convert(self, rwx, base_matrix=None, base_material=None):
        if(base_matrix is None):
            base_matrix = numpy.identity(4)

        matrix_stack = [base_matrix,]
        if "transforms" in rwx:
            for transform in rwx['transforms']:
                if(transform['type'] == "transform"):
                    matrix = numpy.matrix(transform['matrix']).reshape(4, 4)
                    matrix_stack.append(numpy.dot(matrix, matrix_stack[-1]))
                    
                elif(transform['type'] == "identity"):
                    matrix_stack.append(base_matrix)

                elif(transform['type'] == "scale"):
                    matrix = numpy.identity(4)
                    matrix[0, 0] = transform['x']
                    matrix[1, 1] = transform['y']
                    matrix[2, 2] = transform['z']

                    matrix_stack.append(numpy.dot(matrix, matrix_stack[-1]))

                elif(transform['type'] == "translate"):
                    matrix = numpy.identity(4)
                    matrix[3, :3] = [transform['x'], transform['y'], transform['z']]

                    matrix_stack.append(numpy.dot(matrix, matrix_stack[-1]))

                elif(transform['type'] == "rotate"):
                    x, y, z, rad = (transform['x'], transform['y'], transform['z'],
                                    math.radians(transform['angle']))
                    length = 1 / math.sqrt(x*x + y*y + z*z)
                    x = x * length
                    y = y * length
                    z = z * length

                    s = math.sin(rad)
                    c = math.cos(rad)
                    t = 1 - c

                    matrix = numpy.matrix([[x * x * t + c,
                                            y * x * t + z * s,
                                            z * x * t - y * s,
                                            0.0],
                                           [x * y * t - z * s,
                                            y * y * t + c,
                                            z * y * t + x * s,
                                            0.0],
                                           [x * z * t + y * s,
                                            y * z * t - x * s,
                                            z * z * t + c,
                                            0.0],
                                           [0.0, 0.0, 0.0, 1.0]])

                    matrix_stack.append(numpy.dot(matrix, matrix_stack[-1]))

                else:
                    raise Exception("Unexpected transform %s" % transform['type'])

        # Vertices
        vertex_base_index = len(self.model['vertices']) / 3
        if "vertices" in rwx:
            for vertex in rwx['vertices']:
                vector = numpy.matrix([vertex['x'], vertex['y'], vertex['z'], 1.0,])
                vector_transformed = vector.dot(matrix_stack[vertex['transform']])

                self.model['vertices'] += [
                    vector_transformed.item(0,0),
                    vector_transformed.item(0,1),
                    vector_transformed.item(0,2)
                ]

                self.model['uvs'][0] += [
                    vertex['u'] if 'u' in vertex else 0.0,
                    1-vertex['v'] if 'v' in vertex else 0.0
                ]

        material_cache = []
        if "materials" in rwx:
            if base_material is None:
                composite_material = {
                    'color': [0.0, 0.0, 0.0],
                    'specular': 0.0,
                    'ambient': 0.0,
                    'diffuse': 0.0,
                    'transparency': 1.0,
                    'texture': None
                }
            else:
                composite_material = base_material
            material_cache.append(self.convert_material(composite_material))

            for rwxMaterial in rwx['materials']:
                if(rwxMaterial['type'] == 'surface'):
                    composite_material['ambient'] = rwxMaterial['ambient']
                    composite_material['diffuse'] = rwxMaterial['diffuse']
                    composite_material['specular'] = rwxMaterial['specular']
                elif(rwxMaterial['type'] == 'color'):
                    composite_material['color'] = [rwxMaterial['r'],
                                                   rwxMaterial['g'],
                                                   rwxMaterial['b']]
                elif(any([rwxMaterial['type'] == s for s in ("ambient", "diffuse", "specular",)])):
                     composite_material[rwxMaterial['type']] = rwxMaterial[rwxMaterial['type']]
                elif(rwxMaterial['type'] == "opacity"):
                     composite_material['transparency'] = rwxMaterial['opacity']
                elif(rwxMaterial['type'] == "texture"):
                    composite_material['texture'] = rwxMaterial['texture']

                new_material = self.convert_material(composite_material)

                material_cache.append(new_material)

        if "triangles" in rwx:
            material_index_mapping = {}
            for triangle in rwx['triangles']:
                if triangle['material'] not in material_index_mapping:
                    material_index_mapping[triangle['material']] = len(self.model['materials'])
                    self.model['materials'].append(material_cache[triangle['material']])

                self.model['faces'] += [
                    10,
                    int(triangle['indices'][0]+vertex_base_index-1),
                    int(triangle['indices'][1]+vertex_base_index-1),
                    int(triangle['indices'][2]+vertex_base_index-1),
                    material_index_mapping[triangle['material']],
                    int(triangle['indices'][0]+vertex_base_index-1),
                    int(triangle['indices'][1]+vertex_base_index-1),
                    int(triangle['indices'][2]+vertex_base_index-1),
                ]


        if "children" in rwx:
            for child in rwx["children"]:
                self.convert(child['clump'],
                             matrix_stack[child['transform']],
                             composite_material)


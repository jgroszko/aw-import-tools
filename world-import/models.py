import os, glob
import zipfile

def dirty_float(x):
    try:
        return float(x)
    except ValueError:
        if(x[-1] == '.'):
            return float(x[:-1])

class RwxReader:
    SKIP_KEYWORDS = (
        "texturemodes",
        "texturemode",
        "addtexturemode",
        "removetexturemode",
        "addmaterialmode",
        "removematerialmode",
        "opacityfix",
        "texture",
        "lightsampling",
        "geometrysampling",
        "materialmodes",
        "addhint",
        "hints",
        "axisalignment",
        "sphere",
        "box",
        "texturemipmapstate",
    )

    protos = {}

    def __init__(self, f):
        self.token_gen = self.file_generator(f)

        self.read_rwx()

    def read_line(self):
        return next(self.token_gen, None)

    def file_generator(self, f):
        for line_no, line in enumerate([l.decode('ascii').strip() for l in f]):
            if(line.startswith("#")):
                continue

            self.line_no = line_no
            self.full_line = line

            if "#" in line:
                line = line[:line.index("#")].strip()

            line = line.strip().lower()
            line_split = line.split()
            
            if(len(line_split) <= 0 or
               any([line_split[0] == k for k in self.SKIP_KEYWORDS])):
                continue

            yield (line, line_split)

    def proto_generator(self, proto_name, file_generator):
        for line in self.protos[proto_name]:
            yield line

        yield from file_generator

    def apply_protoinstance(self, proto_name):
        if proto_name not in self.protos:
            raise Exception("Unrecognized proto %s" % proto_name)

        self.token_gen = self.proto_generator(proto_name, self.token_gen)

    def read_proto(self, line):
        name = line.split()[1]

        proto_lines = []
        
        line, line_split = self.read_line()
        while(line_split[0] != "protoend"):
            proto_lines.append((line, line_split,))
            line, line_split = self.read_line()

        self.protos[name] = proto_lines

    def read_clump(self, end_token="clumpend"):
        clump = {
            'transforms': [],
            'materials': [],
            'vertices': [],
            'triangles': [],
            'children': [],
            'tag': 0,
        }

        line, line_split = self.read_line()

        while(line_split[0] != end_token):
            if(line_split[0] == "vertex" or line_split[0] == "vertexext"):
                vertex = {
                    'x': dirty_float(line_split[1]),
                    'y': dirty_float(line_split[2]),
                    'z': dirty_float(line_split[3]),
                    'transform': len(clump['transforms'])
                }
                
                i = 4
                while(i < len(line_split)-4):
                    if(line_split[i] == "uv"):
                        vertex['u'] = dirty_float(line_split[i+1])
                        vertex['v'] = dirty_float(line_split[i+2])
                        i += 3

            elif(line_split[0] == "triangle" or line_split[0] == "triangleext"):
                clump['triangles'].append({
                    'indices': [int(line_split[1]),
                                int(line_split[2]),
                                int(line_split[3]),],
                    'material': len(clump['materials']),
                    'tag': line_split[-1] if line_split[-2] == "tag" else 0
                })

            elif(line_split[0] == "quad" or line_split[0] == "quadext"):
                indices = [int(x) for x in line_split[1:5]]

                clump['triangles'].append({
                    'indices': [indices[0], indices[1], indices[2]],
                    'material': len(clump['materials']),
                    'tag': line_split[-1] if line_split[-2] == "tag" else 0
                })
                clump['triangles'].append({
                    'indices': [indices[2], indices[3], indices[0]],
                    'material': len(clump['materials']),
                    'tag': line_split[-1] if line_split[-2] == "tag" else 0
                })

            elif(line_split[0] == "polygon"):
                count = int(line_split[1])

                indices = [int(line_split[i]) for i in range(2, count+2)]

                for i in range(0, count-1):
                    clump['triangles'].append({
                        'indices': [indices[0], indices[i], indices[i+1]],
                        'material': len(clump['materials']),
                        'tag': line_split[-1] if line_split[-2] == "tag" else 0
                    })
                    
            elif(line_split[0] == "surface"):
                clump['materials'].append({
                    'type': 'surface',
                    'ambient': dirty_float(line_split[1]),
                    'diffuse': dirty_float(line_split[2]),
                    'specular': dirty_float(line_split[3])
                })
            elif(line_split[0] == "color"):
                clump['materials'].append({
                    'type': 'color',
                    'r': dirty_float(line_split[1]),
                    'g': dirty_float(line_split[2]),
                    'b': dirty_float(line_split[3])
                })
            elif(any(line_split[0] == s for s in ("ambient", "diffuse", "specular", "opacity"))):
                clump['materials'].append({
                    'type': line_split[0],
                    line_split[0]: dirty_float(line_split[1])
                })
            elif(line_split[0] == "tag"):
                clump['tag'] = int(line_split[1])

            elif(line_split[0] == "rotate"):
                clump['transforms'].append({
                    'type': 'rotate',
                    'x': dirty_float(line_split[1]),
                    'y': dirty_float(line_split[2]),
                    'z': dirty_float(line_split[3]),
                    'angle': dirty_float(line_split[4])
                })
            elif(line_split[0] == "scale"):
                clump['transforms'].append({
                    'type': 'scale',
                })
            elif(line_split[0] == "translate"):
                clump['transforms'].append({
                    'type': 'translate',
                    'x': dirty_float(line_split[1]),
                    'y': dirty_float(line_split[2]),
                    'z': dirty_float(line_split[3]),
                })
            elif(line_split[0] == "transform" or line_split[0] == "transformjoint"):
                clump['transforms'].append({
                    'type': 'transform',
                    'matrix': [dirty_float(x) for x in line_split[1:17]]
                })
            elif(line_split[0] == "identity" or line_split[0] == "identityjoint"):
                clump['transforms'].append({
                    'type': 'identity'
                })

            elif(line_split[0] == "protobegin"):
                self.read_proto(line)
            elif(line_split[0] == "protoinstance"):
                self.apply_protoinstance(line_split[1])

            elif(any(line_split[0] == s for s in
                     ("clumpbegin", "transformbegin", "jointtransformbegin",))):
                type = line_split[0][:-5]
                clump['children'].append({
                    'type': type,
                    'transform': len(clump['transforms']),
                    'clump': self.read_clump(type + "end")
                })
            else:
                raise Exception("Unexpected %s, line %d\n%s" % (line_split[0], self.line_no, self.full_line))

            line, line_split = self.read_line()

        return clump

    def read_rwx(self):
        line, line_split = self.read_line()

        if(line_split[0] == "modelbegin"):
            self.model = self.read_clump("modelend")


def models_import(path):
    os.chdir(path)
    for file in glob.glob("*.zip"):
        if zipfile.is_zipfile(file):
            print("Unzipping ", file)

            zf = zipfile.ZipFile(file)

            try:
                model_name = next(name for name in zf.namelist() if name.endswith(".rwx"))

                print("Reading %s from zip" % model_name)

                f = zf.open(model_name)
                try:
                    rwx = RwxReader(f)
                finally:
                    f.close()

            finally:
                zf.close()

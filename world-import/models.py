import os, glob
import zipfile

class RwxReader:
    SKIP_KEYWORDS = (
        "texturemodes",
        "addtexturemode",
        "removetexturemode",
        "addmaterialmode",
        "removematerialmode",
        "opacity",
        "texture",
        "lightsampling",
        "geometrysampling",
        "materialmodes",
        "addhint",
        "hints"
    )

    protos = {}

    def __init__(self, f):
        self.token_gen = self.file_generator(f)

        self.read_rwx()

    def read_word_full(self):
        return next(self.token_gen, None)

    def read_word(self, expecting = None):
        word = next(self.token_gen, None)[0]

        if(word is None):
            raise Exception("Unexpected end of file")

        if(expecting is not None and
           word is not expecting):
            raise Exception("Unexpected %s", word)

        return word

    def read_int(self):
        word = next(self.token_gen, None)[0]

        return int(word)


    def read_float(self):
        word = next(self.token_gen, None)[0]

        return float(word)

    def file_generator(self, f):
        for line_no, line in enumerate([l.decode('ascii').strip() for l in f]):
            if(line.startswith("#")):
                continue

            self.line_no = line_no
            self.full_line = line

            if "#" in line:
                line = line[:line.index("#")].strip()

            if(not any([line.lower().startswith(k)
                        for k in self.SKIP_KEYWORDS])):
                for word in line.split():
                    result = (word.lower(), line, line_no)
                    yield result

    def proto_generator(self, proto_name, file_generator):
        for word in self.protos[proto_name]:
            yield word

        yield from file_generator

    def apply_protoinstance(self, proto_name):
        if proto_name not in self.protos:
            raise Exception("Unrecognized proto %s" % proto_name)

        self.token_gen = self.proto_generator(proto_name, self.token_gen)

    def read_proto(self):
        name =self.read_word()

        proto_words = []
        
        word = self.read_word_full()
        while(word[0].lower() != "protoend"):
            proto_words.append(word)
            word =self.read_word_full()

        self.protos[name] = proto_words

    def read_clump(self, end_token="clumpend"):
        clump = {
            'transforms': [],
            'materials': [],
            'vertices': [],
            'triangles': [],
            'children': [],
            'tag': 0,
        }

        word_full = self.read_word_full()
        word = word_full[0]
        while(word != end_token):
            if(word == "vertex"):
                vertex = {
                    'x': self.read_float(),
                    'y': self.read_float(),
                    'z': self.read_float(),
                    'transform': len(clump['transforms'])
                }

                remaining_terms = len(word_full[1].split())-5
                while(remaining_terms > 0):
                    word_full = self.read_word_full()
                    word = word_full[0]

                    if(word_full[0] == "uv"):
                        vertex['u'] = self.read_float()
                        vertex['v'] = self.read_float()
                        remaining_terms = remaining_terms - 2

            elif(word == "triangle"):
                clump['triangles'].append({
                    'indices': [self.read_int(), self.read_int(), self.read_int()],
                    'material': len(clump['materials'])
                })

            elif(word == "quad" or word == "quadext"):
                indices = [self.read_int(), self.read_int(), self.read_int(), self.read_int()]

                clump['triangles'].append({
                    'indices': [indices[0], indices[1], indices[2]],
                    'material': len(clump['materials'])
                })
                clump['triangles'].append({
                    'indices': [indices[2], indices[3], indices[0]],
                    'material': len(clump['materials'])
                })

            elif(word == "polygon"):
                count = self.read_int()

                indices = [self.read_int() for _ in range(0, count)]

                for i in range(0, count-1):
                    clump['triangles'].append({
                        'indices': [indices[0], indices[i], indices[i+1]],
                        'material': len(clump['materials'])
                    })
                    
            elif(word == "surface"):
                clump['materials'].append({
                    'type': 'surface',
                    'ambient': self.read_float(),
                    'diffuse': self.read_float(),
                    'specular': self.read_float()
                })
            elif(word == "color"):
                clump['materials'].append({
                    'type': 'color',
                    'r': self.read_float(),
                    'g': self.read_float(),
                    'b': self.read_float()
                })
            elif(word == "ambient"):
                clump['materials'].append({
                    'type': 'ambient',
                    'ambient': self.read_float(),
                })
            elif(word == "diffuse"):
                clump['materials'].append({
                    'type': 'diffuse',
                    'diffuse': self.read_float(),
                })
            elif(word == "specular"):
                clump['materials'].append({
                    'type': 'specular',
                    'specular': self.read_float(),
                })
            elif(word == "tag"):
                clump['tag'] = self.read_int()

            elif(word == "rotate"):
                clump['transforms'].append({
                    'type': 'rotate',
                    'x': self.read_float(),
                    'y': self.read_float(),
                    'z': self.read_float(),
                    'angle': self.read_float()
                })
            elif(word == "scale"):
                clump['transforms'].append({
                    'type': 'scale',
                    'x': self.read_float(),
                    'y': self.read_float(),
                    'z': self.read_float()
                })
            elif(word == "translate"):
                clump['transforms'].append({
                    'type': 'translate',
                    'x': self.read_float(),
                    'y': self.read_float(),
                    'z': self.read_float()
                })
            elif(word == "transform"):
                clump['transforms'].append({
                    'type': 'transform',
                    'matrix': [self.read_float() for _ in range(0, 16)],
                })
            elif(word == "identity"):
                clump['transforms'].append({
                    'type': 'identity'
                })
            elif(word == "identityjoint"):
                clump['transforms'].append({
                    'type': 'identity'
                })

            elif(word == "protobegin"):
                self.read_proto()
            elif(word == "protoinstance"):
                self.apply_protoinstance(self.read_word())

            elif(word == "clumpbegin"):
                clump['children'].append({
                    'type': 'clump',
                    'transform': len(clump['transforms']),
                    'clump': self.read_clump()
                })
            elif(word == "transformbegin"):
                clump['children'].append({
                    'type': 'transform',
                    'transform': len(clump['transforms']),
                    'group': self.read_clump("transformend")
                })
            elif(word == "jointtransformbegin"):
                clump['children'].append({
                    'type': 'transform',
                    'transform': len(clump['transforms']),
                    'group': self.read_clump("jointtransformend")
                })
            else:
                raise Exception("Unexpected %s, line %d\n%s" % (word, self.line_no, self.full_line))

            word_full = self.read_word_full()
            word = word_full[0]

        return clump

    def read_rwx(self):
        word = self.read_word()

        if(word == "modelbegin"):
            model = self.read_clump("modelend")

            print("Read model")
        

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

import os, glob
import zipfile

from rwxreader import RwxReader
from rwxtothree import RwxToThree

def models_import(path):
    os.chdir(path)
    for file in glob.glob("*.zip"):
        if zipfile.is_zipfile(file):
            zf = zipfile.ZipFile(file)

            try:
                model_file = next(name for name in zf.namelist() if name.endswith(".rwx"))
                model_name = os.path.splitext(model_file)[0]

                print("Reading %s from zip" % model_file)

                f = zf.open(model_file)
                try:
                    rwx = RwxReader(f)
                    three = RwxToThree(rwx.model)

                    three.write_json(model_name + ".json")
                finally:
                    f.close()

            finally:
                zf.close()

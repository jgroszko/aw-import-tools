import os, glob
import zipfile

from rwxreader import RwxReader

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

import sys, os

from models import models_import

def world_import(path):
    models_import(os.path.join(path, "models"))

if __name__=='__main__':
    world_import(sys.argv[1])

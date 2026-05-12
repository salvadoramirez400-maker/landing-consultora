import sys
import os

sys.path.insert(0, "/root/consultorias-clinicas")
os.chdir("/root/consultorias-clinicas")

from app import app as application

import tomllib as tml
import tomli_w as tw
import json

class PyProject:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.data = tml.load(f)
        
    @staticmethod
    def create(path):
        with open(path, "wb") as f:
            tw.dump({}, f)
        return PyProject(path)

    def save(self):
        with open(self.path, "wb") as f:
            tw.dump(self.data, f)
        
    def get(self, key):
        return self.data[key]
    
    def set(self, key, value):
        self.data[key] = value
        
    def remove(self, key):
        del self.data[key]
        
    def __str__(self):
        return tw.dumps(self.data)
    
    def __getitem__(self, key):
        return self.get(key)
    
    def __setitem__(self, key, value):
        return self.set(key, value)
        
    def __delitem__(self, key):
        return self.remove(key)


      
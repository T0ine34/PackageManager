import argparse
import importlib.metadata as metadata
import sys
import virtualenv
import subprocess as sp
import os
import re

try:
    from .config_file import PyProject
except ImportError:
    from config_file import PyProject

try:
    VERSION = metadata.version("PackageManager")
except metadata.PackageNotFoundError:
    VERSION = "0.0.0"
    

if sys.platform == "win32":
    BIN_FOLDER = "Scripts"
else:
    BIN_FOLDER = "bin"


GLOBAL_PYTHON_EXECUTABLE = sys.executable #path to the python executable
GLOBAL_PIP_EXECUTABLE = f"{GLOBAL_PYTHON_EXECUTABLE} -m pip" #path to the pip executable

DEFAULT_CONFIG_PATH = "test.config.toml" #a file with the same structure as a pyproject.toml file


class PackageManager:
    def __init__(self, config_path : str):
        self.configPath = config_path
        self.envPath = ".ppm.env"
    
    def init(self, name : str, authors : str, description : str):        
        def createPyProject():
            if not name:
                name = input("Enter the name of the package: ")
            if not authors:
                authors = input("Enter the authors of the package: ")
            if not description:
                description = input("Enter the description of the package: ")
            
            config = PyProject.create(self.configPath)
            config.set("build-system", {"requires": ["setuptools>=61.0"], "build-backend": "setuptools.build_meta"})
            config.set("project", {
                "name": name,
                "dynamic": ["version"],
                "authors" : list(map(str.strip, authors.split(","))),
                "description": description,
                "readme": "README.md",
                "dependencies": [],
                })
            
            config.save()
        
        def createVenv():
            virtualenv.cli_run([self.envPath])
            activate_this = f"{self.envPath}/{BIN_FOLDER}/activate_this.py"
            with open(activate_this) as f:
                exec(f.read(), {"__file__": activate_this})
        
    
        if os.path.exists(self.configPath):
            print("A config file already exists. Do you want to overwrite it? (y/n):", end=" ")
            if input().lower() == "y":
                createPyProject()
        createVenv()
        print("Initialization complete")
            

    def install(self, name : str, _global : bool):
        config = PyProject(self.configPath)
        
        if not os.path.exists(self.envPath):
            print("No environment found. Please run 'init' first")
            return
        
        def getInstalledPackages():
            if _global:
                res = sp.run([GLOBAL_PIP_EXECUTABLE, "freeze"], capture_output=True)
            else:
                res = sp.run([f"{self.envPath}/{BIN_FOLDER}/pip", "freeze"], capture_output=True)
            
            if res.returncode != 0:
                raise Exception("Failed to get installed packages (exit code: {res.returncode})")
            
            return res.stdout.decode().split("\n")
        
        def installPackage(package : str):
            if _global:
                return os.system(f"{GLOBAL_PIP_EXECUTABLE} install {package}")
            else:
                # res = os.system(f"{self.envPath}/{BIN_FOLDER}/pip install {package}")
                res = sp.run([f"{self.envPath}/{BIN_FOLDER}/pip", "install", package], capture_output=True)
                if res.returncode != 0:
                    return res.returncode
                
                stdout = res.stdout.decode()
                if stdout.startswith("Requirement already satisfied"):
                    return 0
                
                for line in stdout.split("\n"):
                    if line.startswith("Successfully installed"):
                        packages = line.split(" ")[2:]
                        for package in packages:
                            name, version = package.split("-")
                            versionString = f"{name}=={version}"
                            if versionString not in config["project"]["dependencies"]:
                                config["project"]["dependencies"].append(versionString)
                            print(f"Installed {name}=={version}")
                config.save()
                return 0
        
        installedPackages = getInstalledPackages()
        if not name:
            # install all dependencies in the config file
            deps = config["project"]["dependencies"]
            
            print(f"Installing {len(deps)} dependencies")
            for dep in deps:
                if dep not in installedPackages:
                    installPackage(dep)
                else:
                    print(f"Dependency {dep} is already installed")
        else:
            installPackage(name)
            

    def uninstall(self, name : str, _global : bool):
        if not os.path.exists(self.envPath):
            print("No environment found. Please run 'init' first")
            return
        
        config = PyProject(self.configPath)
        
        if _global:
            return os.system(f"{GLOBAL_PIP_EXECUTABLE} uninstall -y {name}")
        else:
            res = sp.run([f"{self.envPath}/{BIN_FOLDER}/pip", "uninstall", "-y", name], capture_output=True)
            
            stdout = res.stdout.decode()
            
            
            if res.returncode != 0:
                print(res.stderr.decode())
                raise Exception(f"Failed to uninstall package {name} (exit code: {res.returncode})")

            for line in stdout.split("\n"):
                if line.startswith("Uninstalling"):
                    package = line.split(" ")[1]
                    if package.endswith(":"):
                        package = package[:-1]
                    name, version = package.split("-")
                    versionString = f"{name}=={version}"
                    print(f"Uninstalled {name}=={version}")
                    config["project"]["dependencies"].remove(versionString)
            config.save()


    def list(self, _global : bool, deprecated : bool):
        cmd = "list"
        if deprecated:
            cmd += " --outdated"
        
        if _global:
            os.system(f"{GLOBAL_PIP_EXECUTABLE} {cmd}")
        else:
            os.system(f"{self.envPath}/{BIN_FOLDER}/pip {cmd}")
    
    
class ConfigArgParser:
    def init(parser : argparse._SubParsersAction):
        initParser = parser.add_parser("init", help="Initialize a new package")
        initParser.add_argument("name", help="Name of the package", default="", nargs="?")
        initParser.add_argument("authors", help="Authors of the package", default="", nargs="?")
        initParser.add_argument("description", help="Description of the package", default="", nargs="?")
    
    def install(parser : argparse._SubParsersAction):
        installParser = parser.add_parser("install", help="Install a package")
        installParser.add_argument("name", help="Name of the package", default="", nargs="?")
        installParser.add_argument("--global", action="store_true", help="Install the package globally", default=False, dest="_global")

    def uninstall(parser : argparse._SubParsersAction):
        uninstallParser = parser.add_parser("uninstall", help="Uninstall a package")
        uninstallParser.add_argument("name", help="Name of the package", default="")
        uninstallParser.add_argument("--global", action="store_true", help="Uninstall the package globally", default=False, dest="_global")

    def list(parser : argparse._SubParsersAction):
        listParser = parser.add_parser("list", help="List all installed packages")
        listParser.add_argument("--global", action="store_true", help="List all globally installed packages", default=False, dest="_global")
        listParser.add_argument("--deprecated", "--outdated", action="store_true", help="List all deprecated packages", default=False)
        
    

def main():
    parser = argparse.ArgumentParser("PackageManager", description="A package manager similar to npm, but for Python")
    parser.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    parser.add_argument("-c", "--config", help="Path to the pyproject.toml file", default=DEFAULT_CONFIG_PATH)
    commandParser = parser.add_subparsers(dest="command")
    
    ConfigArgParser.init(commandParser)
    ConfigArgParser.install(commandParser)
    ConfigArgParser.uninstall(commandParser)
    ConfigArgParser.list(commandParser)
    
    args = parser.parse_args()
    
    pm = PackageManager(args.config)
    if args.command == "init":
        pm.init(args.name, args.authors, args.description)
    elif args.command == "install":
        pm.install(args.name, args._global)
    elif args.command == "uninstall":
        pm.uninstall(args.name, args._global)
    elif args.command == "list":
        pm.list(args._global, args.deprecated)


if __name__ == "__main__":
    main()
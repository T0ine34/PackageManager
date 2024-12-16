import argparse
import importlib.metadata as metadata
import sys
import virtualenv
import subprocess as sp
import os
from typing import List

from .config_file import PyProject

try:
    VERSION = metadata.version("PackageManager")
except metadata.PackageNotFoundError:
    VERSION = "0.0.0"
    

if sys.platform == "win32":
    BIN_FOLDER = "Scripts"
else:
    BIN_FOLDER = "bin"

PROG_NAME = sys.argv[0]

GLOBAL_PYTHON_EXECUTABLE = sys.executable #path to the python executable
GLOBAL_PIP_EXECUTABLE = f"{GLOBAL_PYTHON_EXECUTABLE} -m pip" #path to the pip executable

DEFAULT_CONFIG_PATH = "test.config.toml" #a file with the same structure as a pyproject.toml file


class PackageManager:
    def __init__(self, config_path : str):
        self.configPath = config_path
        self.envPath = ".ppm.env"
        
    def createPyProject(self, name : str, authors : str, description : str):
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
                "version": "0.1.0",
                "authors" : list(map(str.strip, authors.split(","))),
                "description": description,
                "readme": "README.md",
                "dependencies": [],
                })
            
            config.save()
    
    def createVenv(self):
        virtualenv.cli_run([self.envPath])
        activate_this = f"{self.envPath}/{BIN_FOLDER}/activate_this.py"
        with open(activate_this) as f:
            exec(f.read(), {"__file__": activate_this})
        
    
    def init(self, name : str, authors : str, description : str) -> int:      
        if os.path.exists(self.configPath):
            print("A config file already exists. Do you want to overwrite it? (y/n):", end=" ")
            if input().lower() == "y":
                self.createPyProject(name, authors, description)
        else:
            self.createPyProject(name, authors, description)
        self.createVenv()
        print("Initialization complete")
        return 0
            
    def install(self, name : List[str], _global : bool) -> int:
        config = PyProject(self.configPath)
        
        if not os.path.exists(self.envPath):
            self.createVenv()
        
        def getInstalledPackages():
            if _global:
                res = sp.run([GLOBAL_PIP_EXECUTABLE, "freeze"], capture_output=True)
            else:
                res = sp.run([f"{self.envPath}/{BIN_FOLDER}/pip", "freeze"], capture_output=True)
            
            if res.returncode != 0:
                raise Exception("Failed to get installed packages (exit code: {res.returncode})")
            
            return res.stdout.decode().split("\n")
        
        def installPackage(package : str, version : str = None):
            if version:
                package = f"{package}=={version}"
            if _global:
                res = sp.run([GLOBAL_PIP_EXECUTABLE, "install", package], capture_output=True)
                return res.returncode
            else:
                print(f"Installing {package}")
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
                            name, version = package.rsplit("-", 1)
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
            for package in name:
                if package not in installedPackages:
                    installPackage(package)
                else:
                    print(f"Package {package} is already installed")
        return 0
            
    def uninstall(self, name : List[str], _global : bool) -> int:
        if not os.path.exists(self.envPath):
            print("No environment found")
            return 1
        
        config = PyProject(self.configPath)
        
        if _global:
            res = sp.run([GLOBAL_PIP_EXECUTABLE, "uninstall", "-y", *name], capture_output=True)
            return res.returncode
        else:
            res = sp.run([f"{self.envPath}/{BIN_FOLDER}/pip", "uninstall", "-y", *name], capture_output=True)
            
            stdout = res.stdout.decode()
            
            
            if res.returncode != 0:
                print(res.stderr.decode())
                return res.returncode

            for line in stdout.split("\n"):
                if line.startswith("Uninstalling"):
                    package = line.split(" ")[1]
                    if package.endswith(":"):
                        package = package[:-1]
                    pName, pVersion = package.split("-")
                    versionString = f"{pName}=={pVersion}"
                    print(f"Uninstalled {pName}=={pVersion}")
                    config["project"]["dependencies"].remove(versionString)
            config.save()
            return 0

    def list(self, _global : bool, deprecated : bool) -> int:
        cmd = "list"
        if deprecated:
            cmd += " --outdated"
        
        if _global:
            res = sp.run(f"{GLOBAL_PIP_EXECUTABLE} {cmd}", shell=True)
            if res.returncode != 0:
                print(res.stderr.decode())
                return res.returncode
        else:
            res = sp.run(f"{self.envPath}/{BIN_FOLDER}/pip {cmd}", shell=True)
            if res.returncode != 0:
                print(res.stderr.decode())
                return res.returncode
        return 0
    
    def run(self, script : str, args : List[str]) -> int:
        if not os.path.exists(script):
            print(f"Script {script} not found")
            return 1
        
        if not os.path.exists(self.envPath):
            self.createVenv()
        
        res = sp.run([f"{self.envPath}/{BIN_FOLDER}/python", script, *args])
        return res.returncode
    
class ConfigArgParser:
    @staticmethod
    def init(parser : argparse._SubParsersAction):
        initParser = parser.add_parser("init", help="Initialize a new package")
        initParser.add_argument("name", help="Name of the package", default="", nargs="?")
        initParser.add_argument("authors", help="Authors of the package", default="", nargs="?")
        initParser.add_argument("description", help="Description of the package", default="", nargs="?")
    
    @staticmethod
    def install(parser : argparse._SubParsersAction):
        installParser = parser.add_parser("install", help="Install a package")
        installParser.add_argument("name", help="Name of the package", nargs="*", default="")
        installParser.add_argument("--global", action="store_true", help="Install the package globally", default=False, dest="_global")

    @staticmethod
    def uninstall(parser : argparse._SubParsersAction):
        uninstallParser = parser.add_parser("uninstall", help="Uninstall a package")
        uninstallParser.add_argument("name", help="Name of the package", default="", nargs="+")
        uninstallParser.add_argument("--global", action="store_true", help="Uninstall the package globally", default=False, dest="_global")

    @staticmethod
    def list(parser : argparse._SubParsersAction):
        listParser = parser.add_parser("list", help="List all installed packages")
        listParser.add_argument("--global", action="store_true", help="List all globally installed packages", default=False, dest="_global")
        listParser.add_argument("--deprecated", "--outdated", action="store_true", help="List all deprecated packages", default=False)
    
    @staticmethod
    def run(parser : argparse._SubParsersAction):
        runParser = parser.add_parser("run", help="Run a script")
        runParser.add_argument("script", help="Path to the script")
        runParser.add_argument("args", help="Arguments to pass to the script", nargs=argparse.REMAINDER)
    

def main():
    parser = argparse.ArgumentParser(PROG_NAME, description="A package manager similar to npm, but for Python")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("-c", "--config", help="Path to the pyproject.toml file", default=DEFAULT_CONFIG_PATH)
    commandParser = parser.add_subparsers(dest="command")
    
    ConfigArgParser.init(commandParser)
    ConfigArgParser.install(commandParser)
    ConfigArgParser.uninstall(commandParser)
    ConfigArgParser.list(commandParser)
    ConfigArgParser.run(commandParser)
    
    args = parser.parse_args()
    
    pm = PackageManager(args.config)
    if args.command == "init":
        return pm.init(args.name, args.authors, args.description)
    elif args.command == "install":
        return pm.install(args.name, args._global)
    elif args.command == "uninstall":
        return pm.uninstall(args.name, args._global)
    elif args.command == "list":
        return pm.list(args._global, args.deprecated)
    elif args.command == "run":
        return pm.run(args.script, args.args)
    else:
        print("No command specified")
        parser.print_help()
        sys.exit(1)

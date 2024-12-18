import argparse
import importlib.metadata as metadata
import sys
import virtualenv
import subprocess as sp
import os
from typing import List
import re

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

DEFAULT_CONFIG_PATH = "pyproject.toml" #a file with the same structure as a pyproject.toml file


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
            
    def install(self, names : List[str], _global : bool) -> int:
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
        
        def installPackage(package : str, version : str = None, installDeps : bool = True):
            if version:
                package = f"{package}=={version}"
            if _global:
                cmd = [GLOBAL_PIP_EXECUTABLE, "install", package]
                if installDeps:
                    cmd.append("--no-deps")
                res = sp.run(cmd, capture_output=True)
                print(res.stderr.decode())
                if res.returncode != 0:
                    print(res.stderr.decode())
                    return res.returncode
            else:
                cmd = [f"{self.envPath}/{BIN_FOLDER}/pip", "install", package]
                if installDeps:
                    cmd.append("--no-deps")
                res = sp.run(cmd, capture_output=True)
                if res.returncode != 0:
                    print(res.stderr.decode())
                    return res.returncode
                
                stdout = res.stdout.decode()
                
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
        
        def getMissingDependencies():
            cmd = [f"{self.envPath}/{BIN_FOLDER}/pip", "check"]
            res = sp.run(cmd, capture_output=True)
            if res.returncode != 0:
                raise Exception("Failed to check for missing dependencies")
            missingDeps = re.findall(r"requires (.+?),", res.stdout.decode())
            return missingDeps
            
            
        installedPackages = getInstalledPackages()
        if not names:
            # install all dependencies in the config file
            deps = config["project"]["dependencies"]
            
            print(f"Installing {len(deps)} dependencies")
            for dep in deps:
                if dep not in installedPackages:
                    installPackage(dep, installDeps=False)
                else:
                    print(f"Dependency {dep} is already installed")
        else:
            for package in names:
                if package not in installedPackages:
                    installPackage(package, installDeps=False)
                else:
                    print(f"Package {package} is already installed")
                    
        missingDeps = getMissingDependencies()
        for dep in missingDeps:
            self.install([dep], _global)
                
        return 0
            
    def uninstall(self, names : List[str], _global : bool) -> int:
        """Uninstall a package

        Args:
            names (List[str]): List of package names; can contain the version number (e.g. "requests==2.26.0")
            _global (bool): Whether to uninstall the package globally

        Returns:
            int: 0 if successful, 1 otherwise
        """
        if not os.path.exists(self.envPath):
            print("No environment found")
            return 1
        
        config = PyProject(self.configPath)
        
        if _global:
            res = sp.run([GLOBAL_PIP_EXECUTABLE, "uninstall", "-y", *names], capture_output=True)
            return res.returncode
        else:
            # find the package in the config file
            deps = config["project"]["dependencies"] #are of form "requests==2.26.0"
            #name in names can be of form "requests" or "requests==2.26.0"
            for name in names:
                version = ""
                if "==" in name:
                    if name in deps:
                        deps.remove(name)
                        version = name.split("==")[1]
                    else:
                        print(f"Package {name} not found in dependencies")
                        continue
                else:
                    for dep in deps:
                        if dep.split("==")[0] == name:
                            version = dep.split("==")[1]
                            deps.remove(dep)
                            break
                    else:
                        print(f"Package {name} not found in dependencies")
                        continue
                try:
                    res = sp.run([f"{self.envPath}/{BIN_FOLDER}/pip", "uninstall", "-y", f"{name}=={version}"], capture_output=True)
                    if res.returncode != 0:
                        print(res.stderr.decode())
                        return res.returncode
                except Exception as e:
                    print(e)
                    print(os.path.abspath(f"{self.envPath}/{BIN_FOLDER}/pip"))
                
                print(f"Uninstalled {name}=={version}")
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
    
    def cli(self, _global : bool) -> int:
        if _global:
            res = sp.run(GLOBAL_PYTHON_EXECUTABLE)
        else:
            res = sp.run(f"{self.envPath}/{BIN_FOLDER}/python")
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
        runParser.add_argument("args", help="Arguments to pass to the script", nargs="*", default=[])
    
    @staticmethod
    def cli(parser : argparse._SubParsersAction):
        cliParser = parser.add_parser("cli", help="Open a Python shell in the virtual environment")
        cliParser.add_argument("--global", action="store_true", help="Open a Python shell in the global environment", default=False, dest="_global")


def main():
    parser = argparse.ArgumentParser(PROG_NAME, description="A package manager similar to npm, but for Python")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("-c", "--config", help="Path to the pyproject.toml file", default=DEFAULT_CONFIG_PATH)
    commandParser = parser.add_subparsers(dest="command")
    
    for func in ConfigArgParser.__dict__.values():
        if callable(func):
            func(commandParser)
    
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
    elif args.command == "cli":
        return pm.cli(args._global)
    else:
        print("No command specified")
        parser.print_help()
        sys.exit(1)

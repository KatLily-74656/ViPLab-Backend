import os, subprocess, dataObjects, json
#sys import to put temp dir relative to main.py
#can be removed when that's a fixed absolute path
import sys
from pycparser import c_parser, c_ast, parse_file

# Path for temp files.
PATH = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "temp")
# Keeps files created in temp folder if DEBUG = True
DEBUG = True

class C:
    """ Class for processing, compiling, running and evaluating C code.

    Attributes:
        solution (Solution):
            Solution object storing data from solution json and the corresponding exercise object
        result (Result):
            Result object storing evaluation data generated by this class.
    """
    def __del__(self):
        """ Destructor deletes files in temp folder after execution 
        """
        if os.path.isdir(PATH) and not DEBUG:
            for f in os.scandir(PATH):
                os.remove(f.path)
            print("temp folder cleared")

    def __init__(self, solution : dataObjects.Solution):
        """ Constructor

        Args:
            solution (Solution):
                The solution object storing data from solution json and exercise object
        """
        self.result = dataObjects.Result(dataObjects.readJson(solution.createJson()))
        self.solution = solution
        self._lang = self.solution.exercise.lang
        self._fileext = "c" if self._lang == "C" else "cpp"

    def processData(self):
        """ Processes code, generates files and runs them to get a result.
        """
        # Creates temp dir if it does not exist
        if not os.path.exists(PATH):
            os.makedirs(PATH)
            print("created temp folder")

        # Prepare code by replacing placeholder code with solutions code
        self.replaceCodeWithSolution()

        maxState = self.getMaxState()
        #maxState = 2 # For testing
        # Step 1: Merge source code
        self.fileInfo = self.merge()
        #print(f"fileInfo:\n{json.dumps(self.fileInfo, indent = 2)}")
        # Step 2: Compile files containing source code
        exitcode = 0
        if 1 <= maxState:
            exitcode = self.compile()
        # Step 3 (Only C): Check if student's solution contains illegal calls
        if exitcode == 0 and 2 <= maxState and self._lang == "C":
            exitcode = self.check()
        # Step 4: Link compiled files and libraries
        if exitcode == 0 and 3 <= maxState:
            exitcode = self.link()
        # Step 5: Run exectutable files
        if exitcode == 0 and 4 <= maxState:
            self.run()

        # Data for result object
        self.result.calculateComputationTime()

    def getMaxState(self) -> int:
        """ Retrieves max state of data processing 

        Returns:
            An integer representing the max state 
        """
        s = self.solution.exercise.config[self._lang].get("stopAfterPhase")
        return 4 if s is None or s == "running" else \
            3 if s == "linking" else \
            2 if s == "checking" else \
            1 if s == "compiling" else 0
    
    def replaceCodeWithSolution(self):
        """ Modifying exercise code by replacing placeholder code with student solution
        """
        for sEl in self.solution.exerciseModifications["elements"]:
            for eEl in self.solution.exercise.elements:
                if eEl["identifier"] == sEl["identifier"] and eEl["modifiable"] == True:
                    eEl["value"] = sEl["value"]
                    break

    def merge(self) -> dict:
        """ Merges all code snippets given by exercise json in config.merging

        Returns:
            A dict containing one dict per merged source file.
                - key: filename (without extension)
                - value: dict
            The structure of each of these dicts describing source files:
                - key: identifier of code snippet
                - value: dict containing following (keys: values):
                    - "visible": Bool indicating if section is visible for student
                    - "start": Integer indicating Start of Section (line number)
                    - "stop": Integer indicating End of Section (line number)
        """
        if len(self.solution.exercise.config[self._lang]["merging"]) == 1:
            return self.mergeSingleFile()
        else:
            return self.mergeMultipleFiles()

    def mergeSingleFile(self) -> dict:
        """ Merges a single file.

        Returns:
            A dict as specified as in "merge".
            The filename is always "temp"
        """
        r = {"temp" : {}}
        code = ""
        loc = 0
        for s in self.solution.exercise.config[self._lang]["merging"]["sources"]:
            for e in self.solution.exercise.elements:
                if s == e["identifier"]:
                    r["temp"][s] = {}
                    r["temp"][s]["visible"] = e["visible"]
                    r["temp"][s]["start"] = (loc + 1)
                    code += e["value"]
                    if not code.endswith("\n"):
                        code += "\n"
                    cnt = e["value"].count("\n")
                    loc += cnt
                    r["temp"][s]["stop"] = loc if cnt != 0 else (loc + 1)
                    break
        loc += 1
        with open(os.path.join(PATH, f"temp.{self._fileext}"), "w+") as f:
            f.write(code)
        return r

    def mergeMultipleFiles(self) -> dict:
        """ Merges multiple files.

        Returns:
            A dict as specified as in "merge".
        """
        r = {}
        for m in self.solution.exercise.config[self._lang]["merging"]:
            fname = m["mergeID"] 
            loc = 0
            r[fname] = {}
            code = ""
            for s in m["sources"]:
                for e in self.solution.exercise.elements:
                    if s == e["identifier"]:
                        r[fname][s] = {}
                        r[fname][s]["visible"] = e["visible"]
                        r[fname][s]["start"] = (loc + 1)
                        code += e["value"]
                        if not code.endswith("\n"):
                            code += "\n"
                        cnt = e["value"].count("\n")
                        loc += cnt
                        r["temp"][s]["stop"] = loc if cnt != 0 else (loc + 1)
                        break
            loc += 1
            with open(os.path.join(PATH, f"{fname}.{self._fileext}"), "w+") as f:
                f.write(code)
        return r

    def compile(self):
        """ Compiles all merged source files.
        """
        files = self.solution.exercise.config[self._lang]["compiling"].get("sources")
        files = files if files is not None else self.fileInfo
        com = f"{self.solution.exercise.getCompilingCommand()} -c " \
            f"{' '.join([os.path.join(PATH, f'{s}.{self._fileext}') for s in files])} " \
            "-fdiagnostics-format=json"
        self.result.computation["technicalInfo"]["compileCommand"] = com
        proc = subprocess.run(com.split(" "), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        parsed = json.loads(proc.stdout.decode("utf-8"))

        if len(parsed) > 0:
            #todo: error and warning informations     
            pass   
        
        data = {
            "MIMEtype":"text/plain",
            "identifier":f"{self.result.id} Compiling",
            "value" : parsed
        }
        self.result.elements.append(data)
        return proc.returncode

    def check(self):
        """ Checks all merged source files.
        Checking after compiling to reduce effort. It's unnecessary to check if compiling fails.
        """
        checker = Checker(self.fileInfo)
        for a in checker.asts:
            checker.getFunctions(checker.asts[a])

        #print(json.dumps(checker.visitor.data, indent=4))

        data = {
            "MIMEtype":"text/plain",
            "identifier":f"{self.result.id} Checking",
            "value" : ""
        }
        self.result.elements.append(data)
        return 0

    def link(self):
        """ Links compiled files and libraries.
        """
        flags = self.solution.exercise.config[self._lang]["linking"]["flags"]
        com = "gcc" if self._lang == "C" else "g++"
        com += f" -o out {' '.join([os.path.join(PATH, f'{s}.o') for s in self.fileInfo])} {flags}"
        self.result.computation["technicalInfo"]["linkCommand"] = com
        proc = subprocess.run(com.split(" "), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        data = {
            "MIMEtype":"text/plain",
            "identifier":f"{self.result.id} Linking",
            "value" : proc.stdout.decode("utf-8")
        }
        self.result.elements.append(data)
        return proc.returncode
    
    def run(self):
        """ Makes file executable and runs it.
        """
        os.chmod("out", 0o700)
        com = os.path.join(PATH, "out")
        self.result.computation["technicalInfo"]["runCommand"] = com
        proc = subprocess.run(com.split(" "), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        data = {
            "MIMEtype":"text/plain",
            "identifier":f"{self.result.id} Running",
            "value" : proc.stdout.decode("utf-8")
        }
        self.result.elements.append(data)

class Checker:
    """ Class for generating Abstract Syntax Trees (AST) of source files
        and retrieving informations about function calls.
    
    Attributes:
        asts (dict):
            A dict containing one entry for each merged source file
                - key: filename (without extension)
                - value: AST of source file
    """

    def __init__(self, files: dict):
        """ Constructor

        Args:
            files (dict):
                A dict generated by the "merge" function in class "C"
        """
        self._files = files
        self.asts = self.getAsts()
        self.visitor = self.Visitor()

    class Visitor(c_ast.NodeVisitor):
        """ Internal Class for visiting nodes in an AST.
        """
        def __init__(self):
            self.data = {}
        
        def visit_FuncDef(self, node):
            """ Finds and prints all found function calls in a function
            """
            if node.decl.coord.file not in self.data:
                self.data[node.decl.coord.file] = {}
            self.data[node.decl.coord.file][node.decl.name] = {}
            #print(f"File: {node.decl.coord.file}")
            i = 0
            for n in node.body.block_items:
                if isinstance(n, c_ast.FuncCall):
                    self.data[node.decl.coord.file][node.decl.name][str(i)] = {
                        "FuncCall" : n.name.name,
                        "Line" : n.coord.line,
                        "Column" : n.coord.column
                    }
                    i += 1

    def getAst(self, filename) -> c_ast.FileAST:
        """ Generates an AST from given source file

        Args:
            filename (str):
                The name of the source file to generate an AST for
        """
        fake_libc_include = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 
            'utils', 'fake_libc_include')
        return parse_file(filename, use_cpp=True, cpp_path="gcc",
            cpp_args=["-E", f"-I{fake_libc_include}"])

    def getAsts(self) -> dict:
        """ Generates one AST for each merged source file

        Returns:
            A dict containing one (key, value) pair for each source file.
                - key: filename (without extension)
                - value: AST for the corresponding file
        """
        asts = {}
        for f in self._files:
            asts[f] = self.getAst(os.path.join(PATH, f"{f}.c"))
        return asts
    
    def getFunctions(self, ast: c_ast.FileAST):
        """ Iterates over the given AST and visit nodes as specified as in Visitor class
        Args:
            ast:
                An AST representing a source file.
        """
        self.visitor.visit(ast)
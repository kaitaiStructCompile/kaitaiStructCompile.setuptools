import os
import warnings
from distutils.cmd import Command
from importlib import import_module
from pathlib import Path
import json
from copy import deepcopy

import setuptools

from .backendSelector import selectBackend
from .colors import styles
from .ICompiler import InFileCompileResult, InMemoryCompileResult, PostprocessResult
from .postprocessors import postprocessors
from .schemas import schema
from .utils import *

try:
	from .schemas.validators import validator
except ImportError as ex:
	validator = None
	warnings.warn("Cannot import kaitaiStructCompile.schemas: " + str(ex) + " . Skipping JSONSchema validation...")


def empty(o, k):
	return k not in o or not o[k]


def prepareFdir(fdir):
	if empty(fdir, "update"):
		fdir["update"] = schema["definitions"]["formatsRepo"]["properties"]["update"]["default"]

	if empty(fdir, "git"):
		fdir["git"] = schema["definitions"]["formatsRepo"]["properties"]["git"]["default"]

	if empty(fdir, "refspec"):
		fdir["refspec"] = schema["definitions"]["formatsRepo"]["properties"]["refspec"]["default"]

	if empty(fdir, "localPath"):
		if fdir["update"]:
			localDirName = os.path.basename(fdir["git"])
			a = os.path.splitext(localDirName)
			if len(a) > 1 and a[-1] == ".git":
				localDirName = a[0]

			fdir["localPath"] = Path(".") / localDirName
		else:
			fdir["localPath"] = None


def prepareCompilerFlags(flags):
	if empty(flags, "additionalFlags"):
		flags["additionalFlags"] = schema["definitions"]["additionalFlags"]["default"]
		if empty(flags, "namespaces"):
			flags["namespaces"] = schema["definitions"]["namespacesSpec"]["default"]


def prepareCfg(cfg):
	if empty(cfg, "postprocessors"):
		cfg["postprocessors"] = type(postprocessors)(postprocessors)

	if empty(cfg, "tolerableIssues"):
		cfg["tolerableIssues"] = schema["properties"]["tolerableIssues"]["default"]

	if empty(cfg, "forceBackend"):
		cfg["forceBackend"] = schema["properties"]["forceBackend"]["default"]

	if empty(cfg, "kaitaiStructRoot"):
		cfg["kaitaiStructRoot"] = schema["properties"]["kaitaiStructRoot"]["default"]

	if empty(cfg, "search"):
		cfg["search"] = schema["properties"]["search"]["default"]

	if empty(cfg, "flags"):
		cfg["flags"] = {}

	prepareCompilerFlags(cfg["flags"])

	if validator is not None:
		validator.check_schema(cfg)
		validator.validate(cfg)

	prepareFdir(cfg["repo"])

	cfg["inputDir"] = Path(cfg["inputDir"])
	if empty(cfg, "outputDir"):
		if defaultOutDir is None:
			defaultOutDir = cfg["inputDir"]
		cfg["outputDir"] = defaultOutDir
	cfg["outputDir"] = Path(cfg["outputDir"])

	#prepareFormats(cfg)

	if validator is not None:
		validator.check_schema(cfg)
		validator.validate(cfg)


def scanForKsys(cfg) -> None:
	if cfg["search"]:
		for file in cfg["inputDir"].glob("**/*.ksy"):
			cfg["formats"][cfg["outputDir"] / file.parent.relative_to(cfg["inputDir"]) / (file.stem + ".py")] = {"path": file}


def prepareFormats(cfg) -> None:
	scanForKsys(cfg)

	newFormats = type(cfg["formats"])(cfg["formats"])

	for target, descriptor in cfg["formats"].items():
		if not isinstance(target, Path):
			del newFormats[target]
			newFormats[cfg["outputDir"] / target] = descriptor
	cfg["formats"] = newFormats

	for target, descriptor in cfg["formats"].items():
		if not isinstance(descriptor["path"], Path):
			cfg["formats"][target]["path"] = cfg["inputDir"] / descriptor["path"]


helperInitialized = False


def kaitaiTranspilationNeeded(cmd) -> bool:
	print("kaitaiTranspilationNeeded", getattr(cmd.distribution, "kaitai", None))
	return bool(getattr(cmd.distribution, "kaitai", None))


def initializeHelper():
	global helperInitialized

	from distutils.command.build import build

	build.sub_commands.insert(0, ("kaitai_transpile", kaitaiTranspilationNeeded))

	#print("Injected kaitai_transpile into build.sub_commands!")
	helperInitialized = True


def ensureHelperInitialized():
	if not helperInitialized:
		initializeHelper()


def kaitaiHelperSetupPy(dist, keyword, cfg: dict):
	kaitaiCfgInDist = getattr(dist, "kaitai", None)
	if kaitaiCfgInDist is None:
		dist.kaitai = kaitaiCfgInDist = cfg
	else:
		kaitaiCfgInDist.update(cfg)

	ensureHelperInitialized()


def getFromDicHierarchyByPath(dic, path: typing.Iterable[str], default=None):
	cur = dic

	for comp in path:
		cur = cur.get(comp, None)
		if cur is None:
			return default

	return cur


def setToDicHierarchyByPath(dic, path: typing.Iterable[str], v: typing.Any):
	cur = dic

	try:
		for comp in path[:-1]:
			cur1 = cur.get(comp, None)
			if cur1 is None:
				cur1 = cur[comp] = {}
			cur = cur1

		cur[path[-1]] = v
	except:
		#print("setToDicHierarchyByPath error:", path, v)
		raise


def decodeRef(refAddr: str):
	if refAddr[0:2] != "#/":
		raise ValueError
	return refAddr[2:].split("/")


def getSchemaItemByRef(refStr: str):
	path = decodeRef(refStr)
	return getFromDicHierarchyByPath(schema, path)


def walkSchemaUserOptions(schema, callback, prefix: tuple = ()):
	if not schema:
		return

	for k, v in schema.get("properties", {}).items():
		ref = v.get("$ref", None)
		if ref:
			item = getSchemaItemByRef(ref)
			walkSchemaUserOptions(item, callback, prefix + (k,))
		else:
			rT = v.get("type", None)
			if rT:
				if rT == "object":
					walkSchemaUserOptions(v, callback, prefix + (k,))
				else:
					callback(k, v, prefix)


def _schemaToUserOptions(schema):
	res = []

	def appendOpt(k, v, prefix):
		res.append((
			"-".join(prefix + (k,)),
			None,
			v.get("description", None)
		))

	walkSchemaUserOptions(schema, appendOpt)

	return res


compoundJsonTypesNames = {"array", "object"}


class kaitai_transpile(Command):
	description = "Compiles Kaitai Struct specs into code. Not necessarily python one."

	user_options = _schemaToUserOptions(schema)

	def initialize_options(self):
		cfg = deepcopy(getattr(self.distribution, "kaitai", {}))

		def initProp(k, el, prefix):
			path = prefix + (k,)
			propName = "_".join(path)
			v = getFromDicHierarchyByPath(cfg, path)
			if v is None:
				v = el["default"]
			#print("initialize_options", propName, v, el)
			setattr(self, propName, v)

		walkSchemaUserOptions(schema, initProp)
		prepareCfg(cfg)
		self.distribution.kaitai = cfg

	def finalize_options(self):
		cfg = deepcopy(getattr(self.distribution, "kaitai", {}))

		def setOptBack(k, el, prefix):
			path = prefix + (k,)
			propName = "_".join(path)

			rT = el.get("type", None)
			if rT:
				v = getattr(self, propName)
				#print("setOptBack", propName, getFromDicHierarchyByPath(cfg, path), v, el)
				if isinstance(rT, str) and rT in compoundJsonTypesNames and isinstance(el, str):
					v = json.loads(v)
				setToDicHierarchyByPath(cfg, path, v)

		walkSchemaUserOptions(schema, setOptBack)

		prepareCfg(cfg)
		self.distribution.kaitai = cfg

	def run(self):
		cfg = getattr(self.distribution, "kaitai", None)
		if not cfg:
			return

		os.makedirs(str(cfg["outputDir"]), exist_ok=True)

		if cfg["repo"]["update"]:
			from .repo import upgradeLibrary

			upgradeLibrary(cfg["repo"]["localPath"], cfg["repo"]["git"], cfg["repo"]["refspec"], print)

		prepareFormats(cfg)

		ChosenBackend = selectBackend(tolerableIssues=set(cfg["tolerableIssues"]) | getTolerableIssuesFromEnv(), forcedBackend=cfg["forceBackend"])
		compiler = ChosenBackend(progressCallback=print, dirs=cfg["kaitaiStructRoot"], **cfg["flags"], importPath=cfg["repo"]["localPath"])

		for compilationResultFilePath, targetDescr in cfg["formats"].items():
			if "flags" not in targetDescr:
				targetDescr["flags"] = {}

			print(styles["operationName"]("Compiling") + " " + styles["ksyName"](str(targetDescr["path"])) + " into " + styles["resultName"](str(compilationResultFilePath)) + " ...")

			compileResults = compiler.compile([targetDescr["path"]], cfg["outputDir"], additionalFlags=targetDescr["flags"])
			#print(compileResults)

			print(styles["operationName"]("Postprocessing") + " " + styles["resultName"](str(compilationResultFilePath)) + " ...")

			for moduleName, res in compileResults.items():
				if "postprocess" in targetDescr:
					res = PostprocessResult(res, (cfg["postprocessors"][funcName] for funcName in targetDescr["postprocess"]))
				else:
					if isinstance(res, InFileCompileResult):
						savePath = res.path
					else:
						savePath = (compilationResultFilePath.parent / (moduleName + ".py")).absolute()

					if res.needsSave:
						with savePath.open("wt", encoding="utf-8") as f:
							f.write(res.getText())
					else:
						pass  # TODO: find out if we need to move files


def getSetupPyPath() -> Path:
	"""Returns the path of `setup.py` file used to trigger the build."""
	import inspect

	s = inspect.stack()

	setuptoolsDir = Path(setuptools.__file__).absolute().resolve().parent
	s = s[1:]

	setuptoolsFrameFound = None
	for i, f in enumerate(s):
		if f.function == "setup":
			setupFuncFileParentDir = Path(f.filename).absolute().resolve().parent
			if setupFuncFileParentDir == setuptoolsDir:
				setuptoolsFrameFound = i
				break

	if setuptoolsFrameFound is not None:
		setupPyFrame = s[setuptoolsFrameFound + 1]
		fn = Path(setupPyFrame.filename)
		if fn.name == "setup.py":
			return fn.absolute().resolve()


def getSetupPyDir() -> Path:
	"""Returns the path of parent dir of `setup.py`."""
	spp = getSetupPyPath()
	if spp:
		return spp.parent


def kaitaiHelperPyProjectToml(dist: setuptools.dist.Distribution, setupPyDir: str = None, pyProjectTomlSection: dict = None, entryPoint: str = None):
	if setupPyDir is None:
		warnings.warn("You version of setuptools missing facilities for requesting additional data by plugins, (https://github.com/pypa/setuptools/pull/2034), working around ...")
		setupPyDir = getSetupPyDir()
	else:
		setupPyDir = Path(setupPyDir)

	if entryPoint is None:
		entryPointName = "tool.kaitai"
	else:
		entryPointName = entryPoint.name

	if setupPyDir is not None:
		if pyProjectTomlSection is None:
			tomlFile = setupPyDir / "pyproject.toml"
			if tomlFile.is_file():
				import toml

				pyProjectToml = toml.load(setupPyDir / "pyproject.toml")
				pyProjectTomlSection = getFromDicHierarchyByPath(pyProjectToml, entryPointName.split("."), None)

		if pyProjectTomlSection is not None:
			oD = pyProjectTomlSection.get("outputDir", None)
			if oD is not None:
				pyProjectTomlSection["outputDir"] = setupPyDir / oD

			fR = pyProjectTomlSection.get("repo", None)
			if fR is not None:
				lP = fR.get("localPath")
				if lP is not None:
					fR["localPath"] = lP = setupPyDir / lP

					iD = pyProjectTomlSection.get("inputDir", None)
					if iD is not None:
						pyProjectTomlSection["inputDir"] = lP / iD

			dist.kaitai = pyProjectTomlSection
			kaitaiHelperSetupPy(dist, "kaitai", dist.kaitai)

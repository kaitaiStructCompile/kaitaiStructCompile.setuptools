kaitaiStructCompile.setuptools [![Unlicensed work](https://raw.githubusercontent.com/unlicense/unlicense.org/master/static/favicon.png)](https://unlicense.org/)
==============================
[wheel](https://gitlab.com/kaitaiStructCompile.py/kaitaiStructCompile.setuptools/-/jobs/artifacts/master/raw/wheels/kaitaiStructCompile-0.CI-py3-none-any.whl?job=build)
[![PyPi Status](https://img.shields.io/pypi/v/kaitaiStructCompile.setuptools.svg)](https://pypi.python.org/pypi/kaitaiStructCompile.setuptools)
[![GitLab build status](https://gitlab.com/kaitaiStructCompile.py/kaitaiStructCompile.setuptools/badges/master/pipeline.svg)](https://gitlab.com/kaitaiStructCompile.py/kaitaiStructCompile.setuptools/commits/master)
[![Coveralls Coverage](https://img.shields.io/coveralls/KOLANICH/kaitaiStructCompile.setuptools.svg)](https://coveralls.io/r/KOLANICH/kaitaiStructCompile.setuptools)
[![GitLab coverage](https://gitlab.com/kaitaiStructCompile.py/kaitaiStructCompile.setuptools/badges/master/coverage.svg)](https://gitlab.com/kaitaiStructCompile.py/kaitaiStructCompile.setuptools/commits/master)
[![Libraries.io Status](https://img.shields.io/librariesio/github/KOLANICH/kaitaiStructCompile.setuptools.svg)](https://libraries.io/github/KOLANICH/kaitaiStructCompile.setuptools)

This is a `setuptools` plugin (may also work with other PEP517-compliant impls, but not guaranteed) allowing you to just specify `ksy` files you need to compile into python sources in process of building your package in a declarative way.


Usage
-----
Just an add a property `kaitai` into the dict. It is a dict specified and documented with [the JSON Schema](./kaitaiStructCompile/schemas/config.schema.json), so read it carefully.


Here a piece from one project with comments follows:
```toml
[build-system]
requires = ["setuptools>=44", "wheel", "setuptools_scm[toml]>=3.4.3"]
build-backend = "setuptools.build_meta"

[tool.setuptools_scm]

[tool.kaitai]
# Will change in future, see https://github.com/pypa/setuptools/pull/2038
#packageDir = thisDir / "NTMDTRead" # localPath
#outputDir = "kaitai" # rel to packageDir
outputDir = "NTMDTRead/kaitai" # the directory we will put the generated file rel to setup.py dir

search = true
inputDir = "scientific/nt_mdt" # the directory we take KSYs from rel to localPath

[tool.kaitai.formatsRepo]
# we need to get the repo of formats, https://github.com/kaitai-io/kaitai_struct_formats

git = "https://github.com/KOLANICH/kaitai_struct_formats.git"
refspec = "mdt" 
update = true # We need the freshest version to be downloaded from GitHub. We don't need the snapshot shipped with compiler!
localPath = "kaitai_struct_formats" #  Where (rel to `setup.py` dir) the repo will be downloaded and from which location the compiler will use it.


[tool.kaitai.formats]
# here we declare our targets. MUST BE SET, even if empty!!!
```

Or one can pass params to `setup` directly (in this case you set all the paths yourself!!!):

```python
from pathlib import Path
formatsPath=str(Path(__file__).parent / "kaitai_struct_formats") # since the format is in the kaitai_struct_formats repo, we just clone it, but we need its path to show the compiler where the ksy file is. So we put the directory of formats in the current directory.
kaitaiCfg={
	"outputDir": "SpecprParser",
	"inputDir": formatsPath,
	"formatsRepo": {
		"localPath" : formatsPath,
		"update": True
	},
	"formats":{ # here we declare our targets. The key is the resulting file name. The value is the descriptor.
		"specpr.py": {
			"path":"scientific/spectroscopy/specpr.ksy", # the path of the spec within 
			"postprocess":["permissiveDecoding"] # Enumerate here the names of post-processing steps you need. The default ones are in toolbox file. You can also add the own ones by creating in the main scope the mapping name => function.
		}
	}
}

setup(use_scm_version = True, kaitai=kaitaiCfg)
```

Real Examples
-------------

[1](https://gitlab.com/KOLANICH/NTMDTRead/blob/master/setup.py)
[2](https://gitlab.com/KOLANICH/SpecprParser.py/blob/master/setup.py)
[3](https://gitlab.com/KOLANICH/FrozenTable.py/blob/master/setup.py)
[4](https://gitlab.com/KOLANICH/MFCTool.py/blob/master/setup.py)
[5](https://gitlab.com/KOLANICH/RDataParser.py/blob/master/setup.py)

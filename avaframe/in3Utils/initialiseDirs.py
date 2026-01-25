"""
    Setup required directory structures by computational modules
"""

# Load modules
import pathlib
import logging
import uuid

# Local imports
from avaframe.in3Utils import fileHandlerUtils as fU
import avaframe.in3Utils.initializeProject as initProj

# create local logger
# change log level in calling module to DEBUG to see log messages
log = logging.getLogger(__name__)


def initialiseRunDirs(avaDir, modName, cleanRemeshedRasters):
    """ Initialise Simulation run with input data

        Parameters
        ----------
        avaDir : str
            path to avalanche directory
        modName : str
            name of module
        cleanRemeshedRasters: bool
            if True directory Inputs/DEMremeshed shall be cleaned

        Returns
        -------
        workDir : str
            path to Work directory
        outputDir : str
            path to Outputs directory
    """

    # Set directories outputs and current work
    outputDir = pathlib.Path(avaDir, 'Outputs', modName)
    fU.makeADir(outputDir)
    
    # BOJAN: skip this, I don't need this folder (config object not available here, hence commenting out)
    #configDoneDir = pathlib.Path(avaDir, 'Outputs', modName, 'configurationFiles', 'configurationFilesDone')
    #fU.makeADir(configDoneDir)
    
    # BOJAN: add random hash to avoid name duplication
    # BOJAN: Remove workdir
    workDir = None
    #workDir = pathlib.Path(avaDir, 'Work', modName)
    #hash_suffix = uuid.uuid4().hex[:8]  # 8 hex chars
    #workDir = pathlib.Path(avaDir, "Work", f"{modName}_{hash_suffix}")
    
    # If Work directory already exists - error
    #if workDir.is_dir():
    #    message = 'Work directory %s already exists - delete first!' % (workDir)
    #    log.error(message)
    #    raise AssertionError(message)
    #else:
    #    workDir.mkdir(parents=True, exist_ok=False)
    #log.debug('Directory: %s created' % workDir)

    if cleanRemeshedRasters is True:
        initProj.cleanRemeshedDir(avaDir)

    # first clean configurationFilesLatest dir and create new one
    # Bojan I'll just skip this
    # initProj.cleanLatestConfigurationsDirAndCreate(avaDir, modName)

    return workDir, outputDir

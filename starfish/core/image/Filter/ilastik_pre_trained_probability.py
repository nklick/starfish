import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union

import h5py
import numpy as np
import scipy.ndimage as ndi
from skimage.filters import threshold_otsu

from starfish.core.imagestack.imagestack import ImageStack
from ._base import FilterAlgorithm


class IlastikPretrainedProbability(FilterAlgorithm):
    """
    Use an existing ilastik pixel classifier to generate a probability image for a dapi image.
    NOTE: This api may not be used without a downloaded and installed version of Ilastik. Visit
    https://www.ilastik.org/download.html to download.

    Parameters
    ----------
    ilastik_executable: Union[Path, str]
        Path to run_ilastik.sh needed for running ilastik in headless mode. Typically the script is
        located: "/Applications/{ILASTIK_VERSION}/Contents/ilastik-release/run_ilastik.sh"

    ilastik_project: Union[Path, str]
        path to ilastik project .ilp file

    """

    def __init__(self, ilastik_executable: Union[Path, str], ilastik_project: Union[Path, str]):
        ilastik_executable = ilastik_executable \
            if isinstance(ilastik_executable, Path) else Path(ilastik_executable)
        if not ilastik_executable.exists():
            raise EnvironmentError("Can not find run_ilastik.sh. Make sure you've provided the "
                                   "correct location. If you need to download ilastik please"
                                   " visit: https://www.ilastik.org/download.html")
        self.ilastik_executable = ilastik_executable
        self.ilastik_project = ilastik_project

    def run(
            self,
            stack: ImageStack,
            in_place: bool = False,
            verbose: bool = False,
            n_processes: Optional[int] = None,
            *args,
    ) -> Optional[ImageStack]:
        """
        Use a pre trained probability pixel classification model to generate probabilites
        for a dapi image

        Parameters
        ----------
        stack : ImageStack
            Dapi image to be run through ilastik.
        in_place : bool
            N/A
        verbose : bool
            N/A
        n_processes : Optional[int]
            N/A

        Returns
        -------
        ImageStack :
            A new ImageStack created from the cell probabilities provided by ilastik.
        """

        # temp files
        temp_dir = tempfile.TemporaryDirectory()
        dapi_file = f"{temp_dir.name}_dapi.npy"
        output_file = f"{temp_dir.name}_dapi_Probabilities.h5"
        np.save(dapi_file, stack.xarray.values.squeeze())

        # env {} is needed to fix the weird virtualenv stuff
        subprocess.run(
            [self.ilastik_executable,
             '--headless',
             '--project',
             self.ilastik_project,
             "--output_filename_format",
             output_file,
             dapi_file], env={})  # type: ignore

        return self.import_ilastik_probabilities(output_file)

    @classmethod
    def import_ilastik_probabilities(cls, path_to_h5_file: Union[str, Path]
                                     ) -> ImageStack:
        """
        Import cell probabilities provided by ilastik as an ImageStack.

        Parameters
        ----------
        path_to_h5_file : Union[str, Path]
            Path to the .h5 file outputted by ilastik

        Returns
        -------
        ImageStack :
            A new ImageStack created from the cell probabilities provided by ilastik.
        """

        h5 = h5py.File(path_to_h5_file)
        probability_images = h5["exported_data"][:]
        h5.close()
        cell_probabilities, _ = probability_images[:, :, 0], probability_images[:, :, 1]
        cell_threshold = threshold_otsu(cell_probabilities)
        label_array = ndi.label(cell_probabilities > cell_threshold)[0]
        # Add flat dims to make 5d tensor
        label_array = label_array[np.newaxis, np.newaxis, np.newaxis, ...]
        return ImageStack.from_numpy(label_array)

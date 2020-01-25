"""
Parser functions

Copyright (c) Andrew R. McCluskey and Benjamin J. Morgan

Distributed under the terms of the MIT License

@author: Andrew R. McCluskey
"""

# pylint: disable=R0913

# This parser borrows heavily from the
# pymatgen.analysis.diffusion_analyzer.DiffusionAnalyzer
# class, originally authored by Will Richards
# (wrichard@mit.edu) and Shyue Ping Ong.
# We include this statement to not that we make
# no claim to authorship of that code and make
# no attack on the original authors.
#
# In fact, we love pymatgen!

import numpy as np


class PymatgenParser:
    """
    A parser for pymatgen Xdatcar style files.
    """
    def __init__(self, structures, specie, time_step, step_skip,
                 min_obs=30):
        """
        Args:
            structures ([pymatgen.core.structure.Structure]): list of
                pymatgen.core.structure.Structure objects (must be
                ordered in sequence of run). E.g., you may have performed
                sequential VASP runs to obtain sufficient statistics.
            specie (Element/Specie): Specie to calculate diffusivity for
                as a String, e.g. "Li".
            time_step (int): Time step between measurements.
            step_skip (int): Sampling freqency of the displacements
                (time_step is multiplied by this number to get the real
                time between measurements).
            min_obs (int): Minimum number of observations to have before
                including in the MSD vs dt calculation. E.g. If a structure
                has 10 diffusing atoms, and min_obs = 30, the MSD vs dt will
                be calculated up to dt = total_run_time / 3, so that each
                diffusing atom is measured at least 3 uncorrelated times.
        """
        self.time_step = time_step
        self.step_skip = step_skip
        self.indices = []

        structure, disp = _get_structure_and_disp(structures)

        drift_corrected = self.correct_for_drift(structure, disp, specie)

        nsteps = drift_corrected.shape[1]

        timesteps = self.smoothed_timesteps(nsteps, min_obs)

        self.delta_t, self.msd, self.sq_disp_store, self.disp_store = self.get_disps(
            timesteps,
            drift_corrected
        )

    def correct_for_drift(self, structure, disp, specie):
        """
        Perform drift correction

        Args:
            structure (pymatgen.core.structure.Structure): Initial structure.
            disp (array_like): Numpy array of with shape
                [site, time step, axis]
            specie (Element/Specie): Specie to calculate diffusivity for
                as a String, e.g. "Li".

        Returns:
            (array_like) Drift of framework corrected disp.
        """
        framework_indices = []
        for i, site in enumerate(structure):
            if site.specie.symbol == specie:
                self.indices.append(i)
            else:
                framework_indices.append(i)

        # drift corrected position
        framework_disp = disp[framework_indices]
        drift_corrected = disp - np.average(framework_disp, axis=0)[None, :, :]

        return drift_corrected

    def smoothed_timesteps(self, nsteps, min_obs):
        """
        Calculate the smoothed timesteps to be used.

        Args:
            nsteps (int): Number of time steps.
            min_obs (int): Minimum number of observations to have before
                including in the MSD vs dt calculation. E.g. If a structure
                has 10 diffusing atoms, and min_obs = 30, the MSD vs dt will
                be calculated up to dt = total_run_time / 3, so that each
                diffusing atom is measured at least 3 uncorrelated times.

        Returns:
            (array_like) Smoothed timesteps.
        """
        min_dt = int(1000 / (self.step_skip * self.time_step))
        max_dt = min(len(self.indices) * nsteps // min_obs, nsteps)
        if min_dt >= max_dt:
            raise ValueError('Not enough data to calculate diffusivity')
        timesteps = np.arange(
            min_dt,
            max_dt,
            max(int((max_dt - min_dt) / 200), 1),
        )
        return timesteps

    def get_disps(self, timesteps, drift_corrected):
        """
        Calculate the mean-squared displacement

        Args:
            timesteps (array_like): Smoothed timesteps.
            drift_corrected (array_like): Drift of framework corrected disp.

        Returns:
            (array_like, array_like, array_like) Time step intervals,
                mean-squared displacement, and raw squared displacement.
        """
        delta_t = timesteps * self.time_step * self.step_skip

        msd = np.zeros_like(delta_t, dtype=np.double)
        sq_disp_ions = np.zeros(
            (len(drift_corrected), len(delta_t)),
            dtype=np.double)
        sq_disp_store = []
        disp_store = []
        for i, timestep in enumerate(timesteps):
            disp = np.subtract(
                drift_corrected[:, timestep:, :],
                drift_corrected[:, :-timestep, :]
            )
            sq_disp = disp ** 2
            disp_store.append(np.sum(disp, axis=2)[self.indices])
            sq_disp_store.append(np.sum(sq_disp, axis=2)[self.indices])
            sq_disp_ions[:, i] = np.average(np.sum(sq_disp, axis=2), axis=1)
            msd[i] = np.average(sq_disp_ions[:, i][self.indices])

        return delta_t, msd, sq_disp_store, disp_store


def _get_structure_and_disp(structures):
    """
    Obtain the initial structure and displacement from a Xdatcar file

    Args:
        structures ([pymatgen.core.structure.Structure]): list of
                pymatgen.core.structure.Structure objects (must be
                ordered in sequence of run). E.g., you may have performed
                sequential VASP runs to obtain sufficient statistics.

    Returns:
        (pymatgen.core.structure.Structure) Initial structure.
        (array_like) Numpy array of with shape [site, time step, axis]
    """
    coords, latt = [], []
    for i, struct in enumerate(structures):
        if i == 0:
            structure = struct
        coords.append(np.array(struct.frac_coords)[:, None])
        latt.append(struct.lattice.matrix)
    coords.insert(0, coords[0])
    latt.insert(0, latt[0])

    coords = np.concatenate(coords, axis=1)
    d_coords = coords[:, 1:] - coords[:, :-1]
    d_coords = d_coords - np.round(d_coords)
    f_disp = np.cumsum(d_coords, axis=1)
    c_disp = []
    for i in f_disp:
        c_disp.append([np.dot(d, m) for d, m in zip(i, latt[1:])])
    disp = np.array(c_disp)

    # If is NVT-AIMD, clear lattice data.
    if np.array_equal(latt[0], latt[-1]):
        latt = np.array([latt[0]])
    else:
        latt = np.array(latt)

    return structure, disp

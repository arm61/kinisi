"""
This module contains the API classes for :py:mod:`kinisi`. 
It is anticipated that this is where the majority of interaction with the package will occur. 
This module includes the :py:class:`~kinisi.analyze.DiffAnalyzer` class for diffusion analysis, which is compatible with both VASP Xdatcar output files and any MD trajectory that the :py:mod:`MDAnalysis` package can handle. 
"""

# Copyright (c) Andrew R. McCluskey and Benjamin J. Morgan
# Distributed under the terms of the MIT License
# author: Andrew R. McCluskey

import MDAnalysis as mda
from pymatgen.io.vasp import Xdatcar
from kinisi import diffusion
from kinisi.parser import MDAnalysisParser, PymatgenParser


class DiffAnalyzer:
    """
    The :py:class:`kinisi.analyze.DiffAnalyzer` class performs analysis of diffusion relationships in materials. 
    This is achieved through the application of a block bootstrapping methodology to obtain the most statistically accurate values for mean squared displacement and the associated uncertainty. 
    The time-scale dependence of the MSD is then modeled with a straight line Einstein relationship, and Markov chain Monte Carlo is used to quantify inverse uncertainties for this model. 

    Attributes:
        delta_t (:py:attr:`array_like`):  Timestep values. 
        msd (:py:attr:`array_like`): The block bootstrap determined mean squared displacement values.
        msd_err (:py:attr:`array_like`): A upper and lower uncertainty, at a 95 % confidence interval, of the mean squared displacement values.
        msd_distributions (:py:attr:`list` or :py:class:`Distribution`): The distributions describing the MSD at each timestep.
        relationship (:py:class:`kinisi.diffusion.Diffusion`): The :py:class:`~kinisi.diffusion.Diffusion` class object that describes the diffusion Einstein relationship.
        D (:py:class:`uravu.distribution.Distribution`): The gradient of the Einstein relationship divided by 6 (twice the number of dimensions).
        D_offset (:py:class:`uravu.distribution.Distribution`): The offset from the abscissa of the Einstein relationship.

    Args:
        trajectory (:py:attr:`str` or :py:attr:`list` of :py:attr:`str` or :py:attr:`list` of :py:class`pymatgen.core.structure.Structure`): The file path(s) that should be read by either the :py:class:`pymatgen.io.vasp.Xdatcar` or :py:class:`MDAnalysis.core.universe.Universe` classes, or a :py:attr:`list` of :py:class:`pymatgen.core.structure.Structure` objects ordered in sequence of run. 
        params (:py:attr:`dict`): The parameters for the :py:mod:`kinisi.parser` object, which is either :py:class:`kinisi.parser.PymatgenParser` or :py:class:`kinisi.parser.MDAnalysisParser` depending on the input file format. See the appropriate documention for more guidance on this object.  
        dtype (:py:attr:`str`, optional): The file format, for the :py:class:`kinisi.parser.PymatgenParser` this should be :py:attr:`'Xdatcar'` and for :py:class:`kinisi.parser.MDAnalysisParser` this should be the appropriate format to be passed to the :py:class:`MDAnalysis.core.universe.Universe`. Defaults to :py:attr:`'Xdatcar'`.
        bounds (:py:attr:`tuple`, optional): Minimum and maximum values for the gradient and intercept of the diffusion relationship. Defaults to :py:attr:`((0, 100), (-10, 10))`. 
    """
    def __init__(self, trajectory, params, dtype='Xdatcar', bounds=((0, 100), (-10, 10))):  # pragma: no cover
        if dtype is 'Xdatcar':
            xd = Xdatcar(trajectory)
            u = PymatgenParser(xd.structures, **params)
        elif dtype is 'structures':
            u = PymatgenParser(trajectory, **params)
        else:
            universe = mda.Universe(*trajectory, format=dtype)
            u = MDAnalysisParser(universe, **params)

        dt = u.delta_t
        disp_3d = u.disp_3d

        diff_data = diffusion.msd_bootstrap(dt, disp_3d)

        self.dt = diff_data[0]
        self.msd_distributions = diff_data[3]

        self.relationship = diffusion.Diffusion(self.dt, self.msd_distributions, bounds)

        self.msd = self.relationship.y.n
        self.msd_err = self.relationship.y.s[0]

        self.relationship.max_likelihood('diff_evo')
        self.relationship.mcmc()

        self.D = self.relationship.diffusion_coefficient
        self.D_offset = self.relationship.variables[1]


class MSDAnalyzer:
    """
    The :py:class:`kinisi.analyze.MSDAnalyzer` class evaluates the MSD of atoms in a material. 
    This is achieved through the application of a block bootstrapping methodology to obtain the most statistically accurate values for mean squared displacement and the associated uncertainty. 

    Attributes:
        dt (:py:attr:`array_like`):  Timestep values. 
        msd (:py:attr:`array_like`): The block bootstrap determined mean squared displacement values.
        msd_err (:py:attr:`array_like`): A upper and lower uncertainty, at a 95 % confidence interval, of the mean squared displacement values.
        msd_distributions (:py:attr:`list` or :py:class:`Distribution`): The distributions describing the MSD at each timestep.
        relationship (:py:class:`kinisi.diffusion.Diffusion`): The :py:class:`~kinisi.diffusion.Diffusion` class object that describes the diffusion Einstein relationship.

    Args:
        trajectory (:py:attr:`str` or :py:attr:`list` of :py:attr:`str` or :py:attr:`list` of :py:class`pymatgen.core.structure.Structure`): The file path(s) that should be read by either the :py:class:`pymatgen.io.vasp.Xdatcar` or :py:class:`MDAnalysis.core.universe.Universe` classes, or a :py:attr:`list` of :py:class:`pymatgen.core.structure.Structure` objects ordered in sequence of run. 
        params (:py:attr:`dict`): The parameters for the :py:mod:`kinisi.parser` object, which is either :py:class:`kinisi.parser.PymatgenParser` or :py:class:`kinisi.parser.MDAnalysisParser` depending on the input file format. See the appropriate documention for more guidance on this object.  
        dtype (:py:attr:`str`, optional): The file format, for the :py:class:`kinisi.parser.PymatgenParser` this should be :py:attr:`'Xdatcar'` and for :py:class:`kinisi.parser.MDAnalysisParser` this should be the appropriate format to be passed to the :py:class:`MDAnalysis.core.universe.Universe`. Defaults to :py:attr:`'Xdatcar'`.
        bounds (:py:attr:`tuple`, optional): Minimum and maximum values for the gradient and intercept of the diffusion relationship. Defaults to :py:attr:`((0, 100), (-10, 10))`. 
    """
    def __init__(self, trajectory, params, dtype='Xdatcar'):  # pragma: no cover
        if dtype is 'Xdatcar':
            xd = Xdatcar(trajectory)
            u = PymatgenParser(xd.structures, **params)
        elif dtype is 'structures':
            u = PymatgenParser(trajectory, **params)
        else:
            universe = mda.Universe(*trajectory, format=dtype)
            u = MDAnalysisParser(universe, **params)

        dt = u.delta_t
        disp_3d = u.disp_3d

        diff_data = diffusion.msd_bootstrap(dt, disp_3d)

        self.dt = diff_data[0]
        self.msd_distributions = diff_data[3]

        self.relationship = diffusion.Diffusion(self.dt, self.msd_distributions, ((0, 100), (-10, 10)))

        self.msd = self.relationship.y.n
        self.msd_err = self.relationship.y.s[0]


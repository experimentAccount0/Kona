import unittest

import numpy as np

from kona.linalg.memory import KonaMemory
from kona.user.user_solver import UserSolver
from kona.linalg.matrices.lbfgs import LimitedMemoryBFGS
from kona.algorithms.util.linesearch import StrongWolfe, BackTracking
from kona.algorithms.reduced_space_quasi_newton import ReducedSpaceQuasiNewton
from kona.options import BadKonaOption

class QuasiNewtonTestCase(unittest.TestCase):

    def setUp(self):
        solver = UserSolver()
        km = KonaMemory(solver)
        self.pf = km.primal_factory
        self.sf = km.state_factory

        self.pf.request_num_vectors(1)
        self.sf.request_num_vectors(1)

        km.allocate_memory()

    def test_no_quasi_newton(self):

        # primal = self.pf.generate()
        # state = self.sf.generate()

        optns = {'quasi_newton': {'type': None}}
        try:
            ReducedSpaceQuasiNewton(self.pf, self.sf, optns)
        except BadKonaOption as err:
            self.assertEqual(str(err), "Invalid Kona option: optns['quasi_newton']['type'] = None")

        optns = {'quasi_newton': None}
        try:
            ReducedSpaceQuasiNewton(self.pf, self.sf, optns)
        except BadKonaOption as err:
            self.assertEqual(str(err), "Invalid Kona option: optns['quasi_newton']['type'] = None")

        optns = {}
        try:
            ReducedSpaceQuasiNewton(self.pf, self.sf, optns)
        except BadKonaOption as err:
            self.assertEqual(str(err), "Invalid Kona option: optns['quasi_newton']['type'] = None")

        optns = {'quasi_newton': {'type': 25}}
        try:
            ReducedSpaceQuasiNewton(self.pf, self.sf, optns)
        except BadKonaOption as err:
            self.assertEqual(str(err), "Invalid Kona option: optns['quasi_newton']['type'] = 25")

        optns = {'quasi_newton': {'type': BackTracking}}
        try:
            ReducedSpaceQuasiNewton(self.pf, self.sf, optns)
        except BadKonaOption as err:
            self.assertEqual(str(err), "Invalid Kona option: optns['quasi_newton']['type'] = None")


    def test_no_line_search(self):

        optns = {'quasi_newton': {'type': BackTracking}}
        try:
            ReducedSpaceQuasiNewton(self.pf, self.sf, optns)
        except BadKonaOption as err:
            self.assertEqual(str(err), "Invalid Kona option: optns['quasi_newton']['type'] = None")



class HessianApproxTestCase(unittest.TestCase):
    '''Test case for quasi-Newton classes'''

    def assertRelError(self, vec1, vec2, atol=1e-15):
        self.assertTrue(np.linalg.norm(vec1 - vec2) < atol)

    def test_LimitedMemoryBFGS(self):
        # Hessian matrix is [1 0 0; 0 100 0; 0 0 10]
        # initial iterate is [1 1 1] and exact line searches are used
        max_stored = 3
        solver = UserSolver(num_primal=3)
        km = KonaMemory(solver)
        vf = km.primal_factory
        optns = {'max_stored': max_stored}
        lbfgs = LimitedMemoryBFGS(vf, optns)
        vf.request_num_vectors(2)
        km.allocate_memory()

        s_new = vf.generate()
        y_new = vf.generate()
        # first "iteration"
        s_new._data.data[:] = 0.0
        y_new._data.data[:] = 0.0
        s_new._data.data[0] = -1.0
        y_new._data.data[0] = -1.0
        lbfgs.add_correction(s_new, y_new)
        # second "iteration"
        s_new._data.data[:] = 0.0
        y_new._data.data[:] = 0.0
        s_new._data.data[1] = -1.0
        y_new._data.data[1] = -100.0
        lbfgs.add_correction(s_new, y_new)
        # third "iteration"
        s_new._data.data[:] = 0.0
        y_new._data.data[:] = 0.0
        s_new._data.data[2] = -1.0
        y_new._data.data[2] = -10.0
        lbfgs.add_correction(s_new, y_new)

        # testing first column of H*H^{-1}
        s_new._data.data[:] = 0.0
        y_new._data.data[:] = 0.0
        s_new._data.data[0] = 1.0
        lbfgs.solve(s_new, y_new)
        self.assertRelError(y_new._data.data,
                            np.array([1.,0.,0.]), atol=1e-15)
        # testing second column of H*H^{-1}
        s_new._data.data[:] = 0.0
        s_new._data.data[1] = 100.0
        lbfgs.solve(s_new, y_new)
        self.assertRelError(y_new._data.data,
                            np.array([0.,1.,0.]), atol=1e-15)
        # testing second column of H*H^{-1}
        s_new._data.data[:] = 0.0
        s_new._data.data[2] = 10.0
        lbfgs.solve(s_new, y_new)
        self.assertRelError(y_new._data.data,
                            np.array([0.,0.,1.]), atol=1e-15)

if __name__ == "__main__":
    unittest.main()

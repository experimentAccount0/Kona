import unittest

import numpy as np

from kona.linalg.memory import KonaMemory
from kona.user import UserSolver
from kona.linalg.matrices.hessian import LimitedMemoryBFGS
from kona.linalg.matrices.hessian import LimitedMemorySR1

class QuasiNewtonApproxTestCase(unittest.TestCase):

    def assertRelError(self, vec1, vec2, atol=1e-15):
        self.assertTrue(np.linalg.norm(vec1 - vec2) < atol)

    def test_LimitedMemoryBFGS(self):
        '''LimitedMemoryBFGS tests'''
        # Hessian matrix is [1 0 0; 0 100 0; 0 0 10]
        # initial iterate is [1 1 1] and exact line searches are used
        max_stored = 3
        solver = UserSolver(3)
        km = KonaMemory(solver)
        vf = km.primal_factory
        optns = {'max_stored': max_stored}
        lbfgs = LimitedMemoryBFGS(vf, optns)
        vf.request_num_vectors(2)
        km.allocate_memory()

        s_new = vf.generate()
        y_new = vf.generate()
        # first "iteration"
        s_new.base.data[:] = 0.0
        y_new.base.data[:] = 0.0
        s_new.base.data[0] = -1.0
        y_new.base.data[0] = -1.0
        lbfgs.add_correction(s_new, y_new)
        # second "iteration"
        s_new.base.data[:] = 0.0
        y_new.base.data[:] = 0.0
        s_new.base.data[1] = -1.0
        y_new.base.data[1] = -100.0
        lbfgs.add_correction(s_new, y_new)
        # third "iteration"
        s_new.base.data[:] = 0.0
        y_new.base.data[:] = 0.0
        s_new.base.data[2] = -1.0
        y_new.base.data[2] = -10.0
        lbfgs.add_correction(s_new, y_new)

        # testing first column of H*H^{-1}
        s_new.base.data[:] = 0.0
        y_new.base.data[:] = 0.0
        s_new.base.data[0] = 1.0
        lbfgs.solve(s_new, y_new)
        self.assertRelError(y_new.base.data,
                            np.array([1.,0.,0.]), atol=1e-15)
        # testing second column of H*H^{-1}
        s_new.base.data[:] = 0.0
        s_new.base.data[1] = 100.0
        lbfgs.solve(s_new, y_new)
        self.assertRelError(y_new.base.data,
                            np.array([0.,1.,0.]), atol=1e-15)
        # testing third column of H*H^{-1}
        s_new.base.data[:] = 0.0
        s_new.base.data[2] = 10.0
        lbfgs.solve(s_new, y_new)
        self.assertRelError(y_new.base.data,
                            np.array([0.,0.,1.]), atol=1e-15)

    def test_LimitedMemorySR1(self):
        '''LimitedMemorySR1 tests'''
        # Hessian matrix is [1 0 0; 0 100 0; 0 0 -10]
        # initial iterate is [1 1 1] and exact line searches are used
        max_stored = 3
        solver = UserSolver(3)
        km = KonaMemory(solver)
        vf = km.primal_factory
        optns = {'max_stored': max_stored}
        lsr1 = LimitedMemorySR1(vf, optns)
        vf.request_num_vectors(2)
        km.allocate_memory()

        s_new = vf.generate()
        y_new = vf.generate()
        # first "iteration"
        s_new.base.data[:] = 0.0
        y_new.base.data[:] = 0.0
        s_new.base.data[0] = -1.0
        y_new.base.data[0] = -1.0
        lsr1.add_correction(s_new, y_new)
        # second "iteration"
        s_new.base.data[:] = 0.0
        y_new.base.data[:] = 0.0
        s_new.base.data[1] = -1.0
        y_new.base.data[1] = -100.0
        lsr1.add_correction(s_new, y_new)
        # third "iteration"
        s_new.base.data[:] = 0.0
        y_new.base.data[:] = 0.0
        s_new.base.data[2] = -1.0
        y_new.base.data[2] = 10.0
        lsr1.add_correction(s_new, y_new)

        # testing first column of H*H^{-1}
        s_new.base.data[:] = 0.0
        y_new.base.data[:] = 0.0
        s_new.base.data[0] = 1.0
        lsr1.solve(s_new, y_new)
        self.assertRelError(y_new.base.data,
                            np.array([1.,0.,0.]), atol=1e-15)
        # testing second column of H*H^{-1}
        s_new.base.data[:] = 0.0
        s_new.base.data[1] = 100.0
        lsr1.solve(s_new, y_new)
        self.assertRelError(y_new.base.data,
                            np.array([0.,1.,0.]), atol=1e-15)
        # testing third column of H*H^{-1}
        s_new.base.data[:] = 0.0
        s_new.base.data[2] = -10.0
        lsr1.solve(s_new, y_new)
        self.assertRelError(y_new.base.data,
                            np.array([0.,0.,1.]), atol=1e-15)

if __name__ == "__main__":
    unittest.main()

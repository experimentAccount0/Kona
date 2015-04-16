import unittest
import numpy as np

from kona.linalg.memory import KonaMemory
from kona.user import UserSolverIDF
from dummy_solver import DummySolver
from kona.linalg.vectors.composite import ReducedKKTVector

class ReducedKKTVectorTestCase(unittest.TestCase):

    def setUp(self):
        solver = DummySolver(10, 0, 5)
        self.km = km = KonaMemory(solver)

        km.primal_factory.request_num_vectors(3)
        km.dual_factory.request_num_vectors(3)
        km.allocate_memory()

        #can't create bear KonaVectors because the memory manager doesn't
        # like them, so I'll just use the PrimalVector to test the
        # KonaVectorMethods
        self.pv1 = km.primal_factory.generate()
        self.dv1 = km.dual_factory.generate()
        self.pv1._data.data = 2*np.ones(10)
        self.dv1._data.data = 3*np.ones(5)

        self.pv2 = km.primal_factory.generate()
        self.dv2 = km.dual_factory.generate()
        self.pv2._data.data = 2*np.ones(10)
        self.dv2._data.data = 2*np.ones(5)

        self.rkkt_vec1 = ReducedKKTVector(km, self.pv1, self.dv1)
        self.rkkt_vec2 = ReducedKKTVector(km, self.pv2, self.dv2)

    def test_check_type(self):

        try:
            self.rkkt_vec1._check_type(self.pv1)
        except TypeError as err:
            self.assertEquals(str(err), "ReducedKKTVector() >> Wrong vector type. Must be <class 'kona.linalg.vectors.composite.ReducedKKTVector'>")
        else:
            self.fail('TypeError expected')

    def test_bad_init_args(self):

        try:
            ReducedKKTVector(self.km, self.dv1, self.dv1)
        except TypeError as err:
            self.assertEqual(str(err), 'ReducedKKTVector() >> Unidentified design vector.' )
        else:
            self.fail('TypeError expected')

        try:
            ReducedKKTVector(self.km, self.pv1, self.pv1)
        except TypeError as err:
            self.assertEqual(str(err), 'ReducedKKTVector() >> Unidentified dual vector.' )
        else:
            self.fail('TypeError expected')

    def test_equals(self):
        self.rkkt_vec2.equals(self.rkkt_vec1)

        err = self.dv2._data.data - self.dv1._data.data
        self.assertEquals(np.linalg.norm(err), 0)

        err = self.pv2._data.data - self.pv1._data.data
        self.assertEquals(np.linalg.norm(err), 0)

    def test_plus(self):
        self.rkkt_vec2.plus(self.rkkt_vec1)

        err = self.pv2._data.data - 4*np.ones(10)
        self.assertEquals(np.linalg.norm(err), 0)

        err = self.dv2._data.data - 5*np.ones(5)
        self.assertEquals(np.linalg.norm(err), 0)

    def test_minus(self):
        self.rkkt_vec2.minus(self.rkkt_vec1)

        err = self.pv2._data.data - 0*np.ones(10)
        self.assertEquals(np.linalg.norm(err), 0)

        err = self.dv2._data.data - -1*np.ones(5)
        self.assertEquals(np.linalg.norm(err), 0)

    def test_times(self):
        try:
            self.rkkt_vec2.times(self.rkkt_vec1)
        except TypeError as err:
            self.assertEquals(str(err), 'ReducedKKTVector.times() >> Wrong argument type. Must be FLOAT.')

        self.rkkt_vec2.times(3)
        err = self.pv2._data.data - 6*np.ones(10)
        self.assertEquals(np.linalg.norm(err), 0)

        err = self.dv2._data.data - 6*np.ones(5)
        self.assertEquals(np.linalg.norm(err), 0)

        self.rkkt_vec1.times(3.0)
        err = self.pv1._data.data - 6*np.ones(10)
        self.assertEquals(np.linalg.norm(err), 0)

        err = self.dv1._data.data - 9*np.ones(5)
        self.assertEquals(np.linalg.norm(err), 0)

    def test_divide_by(self):

        self.rkkt_vec2.divide_by(2)
        err = self.pv2._data.data - 1*np.ones(10)
        self.assertEquals(np.linalg.norm(err), 0)

        err = self.dv2._data.data - 1*np.ones(5)
        self.assertEquals(np.linalg.norm(err), 0)


    def test_equals_ax_p_by(self):
        self.rkkt_vec2.equals_ax_p_by(2, self.rkkt_vec1, 2, self.rkkt_vec2)

        err = self.pv2._data.data - 8*np.ones(10)
        self.assertEquals(np.linalg.norm(err), 0)

        err = self.dv2._data.data - 10*np.ones(5)
        self.assertEquals(np.linalg.norm(err), 0)

    def test_inner(self):
        ip = self.rkkt_vec2.inner(self.rkkt_vec1)
        self.assertEquals(ip, 70)


    def test_norm2(self):
        ip = self.rkkt_vec2.norm2
        self.assertEquals(ip, 60**.5)

    def test_equals_initial_guess(self):
        self.rkkt_vec2.equals_init_guess()

        err = self.pv2._data.data - 10*np.ones(10)
        self.assertEquals(np.linalg.norm(err), 0)

        err = self.dv2._data.data - 0*np.ones(5)
        self.assertEquals(np.linalg.norm(err), 0)


if __name__ == "__main__":
    unittest.main()
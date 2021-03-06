import unittest

from kona.linalg.memory import KonaMemory
from kona.linalg.vectors.common import DesignVector
from kona.linalg.vectors.composite import CompositeFactory, CompositeVector
from kona.linalg.vectors.composite import CompositePrimalVector, CompositeDualVector
from kona.linalg.vectors.composite import PrimalDualVector, ReducedKKTVector
from kona.user.user_solver import UserSolver

class CompositeFactoryTestCase(unittest.TestCase):

    def test_generate_compositeprimal(self):
        '''CompositeFactory generating CompositePrimalVector'''
        solver = UserSolver(2, 3, 4, 5)
        km = KonaMemory(solver)

        cv_fac = CompositeFactory(km, CompositePrimalVector)
        cv_fac.request_num_vectors(1)

        km.allocate_memory()

        vec = cv_fac.generate()

        self.assertTrue(isinstance(vec, CompositePrimalVector))

    def test_generate_compositedual(self):
        '''CompositeFactory generating CompositeDualVector'''
        solver = UserSolver(2, 3, 4, 5)
        km = KonaMemory(solver)

        cv_fac = CompositeFactory(km, CompositeDualVector)
        cv_fac.request_num_vectors(1)

        km.allocate_memory()

        vec = cv_fac.generate()

        self.assertTrue(isinstance(vec, CompositeDualVector))

    def test_generate_primaldual(self):
        '''CompositeFactory generating PrimalDualVector'''
        solver = UserSolver(2, 3, 4, 5)
        km = KonaMemory(solver)

        cv_fac = CompositeFactory(km, PrimalDualVector)
        cv_fac.request_num_vectors(1)

        km.allocate_memory()

        vec = cv_fac.generate()

        self.assertTrue(isinstance(vec, PrimalDualVector))

    def test_generate_reducedkkt_no_slack(self):
        '''CompositeFactory generating ReducedKKTVector (1/2)'''
        solver = UserSolver(2, 3, 4, 0)
        km = KonaMemory(solver)

        cv_fac = CompositeFactory(km, ReducedKKTVector)
        cv_fac.request_num_vectors(1)

        km.allocate_memory()

        vec = cv_fac.generate()

        self.assertTrue(isinstance(vec, ReducedKKTVector))

    def test_generate_reducedkkt_slack(self):
        '''CompositeFactory generating CompositePrimalVector (2/2)'''
        solver = UserSolver(2, 3, 4, 5)
        km = KonaMemory(solver)

        cv_fac = CompositeFactory(km, ReducedKKTVector)
        cv_fac.request_num_vectors(1)

        km.allocate_memory()

        vec = cv_fac.generate()

        self.assertTrue(isinstance(vec, ReducedKKTVector))

    def test_invalid_memory(self):
        '''CompositeFactory error message for invalid memory object'''
        solver = UserSolver(2, 3, 4, 5)
        try:
            fac = CompositeFactory(solver, ReducedKKTVector)
        except AssertionError as err:
            self.assertEqual(str(err), "Invalid memory object!")

    def test_invalid_type(self):
        '''CompositeFactory error message for invalid vector type (1/6)'''
        solver = UserSolver(2, 3, 4, 5)
        km = KonaMemory(solver)
        try:
            fac = CompositeFactory(km, DesignVector)
        except AssertionError as err:
            self.assertEqual(str(err), "Must provide a CompositeVector-type!")

    def test_compositeprimal_error(self):
        '''CompositeFactory error message for invalid vector type (2/6)'''
        solver = UserSolver(2, 3, 4, 0)
        km = KonaMemory(solver)
        try:
            fac = CompositeFactory(km, CompositePrimalVector)
        except AssertionError as err:
            self.assertEqual(
                str(err), "Cannot generate CompositePrimalVector! No inequality constraints.")

    def test_compositedual_error(self):
        '''CompositeFactory error message for invalid vector type (3/6)'''
        solver = UserSolver(2)
        km = KonaMemory(solver)
        try:
            fac = CompositeFactory(km, CompositeDualVector)
        except AssertionError as err:
            self.assertEqual(
                str(err), 
                "Cannot generate CompositeDualVector! No equality and inequality constraints.")

    def test_primaldual_error(self):
        '''CompositeFactory error message for invalid vector type (4/6)'''
        solver = UserSolver(2)
        km = KonaMemory(solver)
        try:
            fac = CompositeFactory(km, PrimalDualVector)
        except AssertionError as err:
            self.assertEqual(
                str(err), "Cannot generate PrimalDualVector! No constraints.")

    def test_reducedkkt_error(self):
        '''CompositeFactory error message for invalid vector type (5/6)'''
        solver = UserSolver(2)
        km = KonaMemory(solver)
        try:
            fac = CompositeFactory(km, ReducedKKTVector)
        except AssertionError as err:
            self.assertEqual(
                str(err), "Cannot generate ReducedKKTVector! No equality constraints.")

    def test_notimplemented_error(self):
        '''CompositeFactory error message for invalid vector type (6/6)'''
        solver = UserSolver(2)
        km = KonaMemory(solver)
        try:
            fac = CompositeFactory(km, CompositeVector)
        except NotImplementedError as err:
            self.assertEqual(
                str(err), "Factory has not been implemented for given type!")

if __name__ == "__main__":
    unittest.main()

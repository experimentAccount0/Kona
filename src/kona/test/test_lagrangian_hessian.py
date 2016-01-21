import unittest

from kona.examples import Sellar
from kona.linalg.memory import KonaMemory
from kona.linalg.matrices.common import dCdU, dRdU
from kona.linalg.matrices.hessian import LagrangianHessian
from kona.linalg.vectors.composite import ReducedKKTVector
from kona.linalg.vectors.composite import CompositePrimalVector


class LagrangianHessianTestCase(unittest.TestCase):
    '''Test case for the Constrained Hessian approximation matrix.'''

    def _generate_KKT_vector(self):
        design = self.pf.generate()
        slack = self.df.generate()
        primal = CompositePrimalVector(design, slack)
        dual = self.df.generate()
        return ReducedKKTVector(primal, dual)

    def test_constrained_product(self):
        solver = Sellar()
        km = KonaMemory(solver)
        self.pf = km.primal_factory
        self.sf = km.state_factory
        self.df = km.dual_factory

        self.pf.request_num_vectors(6)
        self.sf.request_num_vectors(3)
        self.df.request_num_vectors(11)

        self.W = LagrangianHessian([self.pf, self.sf, self.df])

        km.allocate_memory()

        # get memory
        design_work = self.pf.generate()
        state = self.sf.generate()
        adjoint = self.sf.generate()
        state_work = self.sf.generate()
        dual_work = self.df.generate()
        X = self._generate_KKT_vector()
        dLdX = self._generate_KKT_vector()
        dLdX_pert = self._generate_KKT_vector()
        in_vec = self._generate_KKT_vector()
        out_vec = self._generate_KKT_vector()

        in_vec.equals(2.0)

        X.equals_init_guess()
        state.equals_primal_solution(X._primal._design)
        state_work.equals_objective_partial(X._primal._design, state)
        dCdU(X._primal._design, state).T.product(X._dual, adjoint)
        state_work.plus(adjoint)
        state_work.times(-1.)
        dRdU(X._primal._design, state).T.solve(state_work, adjoint)
        dLdX.equals_KKT_conditions(
            X, state, adjoint, design_work, dual_work)

        epsilon_fd = 1e-6
        X._primal._design.equals_ax_p_by(
            1.0, X._primal._design, epsilon_fd, in_vec._primal._design)
        state.equals_primal_solution(X._primal._design)
        state_work.equals_objective_partial(X._primal._design, state)
        dCdU(X._primal._design, state).T.product(X._dual, adjoint)
        state_work.plus(adjoint)
        state_work.times(-1.)
        dRdU(X._primal._design, state).T.solve(state_work, adjoint)
        dLdX_pert.equals_KKT_conditions(
            X, state, adjoint, design_work, dual_work)

        dLdX_pert.minus(dLdX)
        dLdX_pert.divide_by(epsilon_fd)

        X.equals_init_guess()
        state.equals_primal_solution(X._primal._design)
        state_work.equals_objective_partial(X._primal._design, state)
        dCdU(X._primal._design, state).T.product(X._dual, adjoint)
        state_work.plus(adjoint)
        state_work.times(-1.)
        dRdU(X._primal._design, state).T.solve(state_work, adjoint)
        self.W.linearize(X, state, adjoint)
        self.W.multiply_W(in_vec._primal._design, out_vec._primal._design)

        print '-----------------------------'
        print 'Constrained Hessian'
        print '-----------------------------'
        print 'FD product:'
        print dLdX_pert._primal._design._data.data
        print 'Analytical product:'
        print out_vec._primal._design._data.data
        print '-----------------------------'

        dLdX.equals_ax_p_by(1.0, dLdX_pert, -1.0, out_vec)
        diff_norm = dLdX._primal._design.norm2

        self.assertTrue(diff_norm <= 1e-3)

if __name__ == "__main__":
    unittest.main()
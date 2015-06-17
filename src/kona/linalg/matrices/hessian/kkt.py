import sys, gc
import numpy

from kona.options import get_opt
from kona.linalg.vectors.common import PrimalVector, StateVector, DualVector
from kona.linalg.vectors.composite import ReducedKKTVector
from kona.linalg.matrices.common import dRdX, dRdU, dCdX, dCdU, IdentityMatrix
from kona.linalg.matrices.hessian.basic import BaseHessian, QuasiNewtonApprox
from kona.linalg.solvers.krylov.basic import KrylovSolver
from kona.linalg.solvers.util import calc_epsilon

class ReducedKKTMatrix(BaseHessian):

    def __init__(self, vector_factories, optns={}, approx=False):
        super(ReducedKKTMatrix, self).__init__(vector_factories, optns)

        # read reduced options
        self.product_fac = get_opt(optns, 0.001, 'product_fac')
        self.product_tol = 1.0
        self.lamb = get_opt(optns, 0.0, 'lambda')
        self.scale = get_opt(optns, 1.0, 'scale')
        self.grad_scale = get_opt(optns, 1.0, 'grad_scale')
        self.ceq_scale = get_opt(optns, 1.0, 'ceq_scale')
        self.dynamic_tol = get_opt(optns, False, 'dynamic_tol')

        # get references to individual factories
        self.primal_factory = None
        self.state_factory = None
        for factory in self.vec_fac:
            if factory._vec_type is PrimalVector:
                self.primal_factory = factory
            elif factory._vec_type is StateVector:
                self.state_factory = factory
            elif factory._vec_type is DualVector:
                self.dual_factory = factory

        # preconditioner and solver settings
        self.precond = get_opt(optns, None, 'precond')
        self.krylov = None

        # set flag for approximate KKT Matrix
        self.approx = approx

        # reset the linearization flag
        self._allocated = False

        # request vector memory for future allocation
        self.primal_factory.request_num_vectors(3)
        self.state_factory.request_num_vectors(6)
        self.dual_factory.request_num_vectors(1)

        # initialize abtract jacobians
        self.dRdX = dRdX()
        self.dRdU = dRdU()
        self.dCdX = dCdX()
        self.dCdU = dCdU()

    def _linear_solve(self, rhs_vec, solution, rel_tol=1e-8):
        self.dRdU.linearize(at_design, at_state)
        if not self.approx:
            self.dRdU.solve(rhs_vec, solution, rel_tol=rel_tol)
        else:
            self.dRdU.precond(rhs_vec, solution)

    def _adjoint_solve(self, rhs_vec, solution, rel_tol=1e-8):
        self.dRdU.linearize(at_design, at_state)
        if not self.approx:
            self.dRdU.T.solve(rhs_vec, solution, rel_tol=rel_tol)
        else:
            self.dRdU.T.precond(rhs_vec, solution)

    def set_krylov_solver(self, krylov_solver):
        if isinstance(krylov_solver, KrylovSolver):
            self.krylov = krylov_solver
        else:
            raise TypeError('Solver is not a valid KrylovSolver')

    def set_quasi_newton(self, quasi_newton):
        if isinstance(quasi_newton, QuasiNewtonApprox):
            self.quasi_newton = quasi_newton
        else:
            raise TypeError('Object is not a valid QuasiNewtonApprox')

    @property
    def approx(self):
        self.approx = True
        return self

    def linearize(self, at_design, at_state, at_dual, at_adjoint):

        # store the linearization point
        self.at_design = at_design
        self.primal_norm = self.at_design.norm2
        self.at_state = at_state
        self.state_norm = self.at_state.norm2
        self.at_dual = at_dual
        self.at_adjoint = at_adjoint

        # if this is the first ever linearization...
        if not self._allocated:

            # generate state vectors
            self.adjoint_res = self.state_factory.generate()
            self.w_adj = self.state_factory.generate()
            self.lambda_adj = self.state_factory.generate()
            self.state_work = []
            for i in xrange(3):
                self.state_work.append(self.state_factory.generate())

            # generate primal vectors
            self.pert_design = self.primal_factory.generate()
            self.reduced_grad = self.primal_factory.generate()
            self.primal_work = self.primal_factory.generate()

            # generate dual vectors
            self.dual_work = self.dual_factory.generate()

            self._allocated = True

        # compute adjoint residual at the linearization
        self.adjoint_res.equals_objective_partial(self.at_design, self.at_state)
        self.dRdU.linearize(self.at_design, self.at_state)
        self.dRdU.T.product(self.at_adjoint, self.state_work[0])
        self.adjoint_res.plus(self.state_work[0])
        self.dCdU.linearize(self.at_design, self.at_state)
        self.dCdU.T.product(self.at_dual, self.state_work[0])
        self.adjoint_res.plus(self.state_work[0])

        # compute reduced gradient at the linearization
        self.reduced_grad.equals_objective_partial(self.at_design, self.at_state)
        self.dRdX.linearize(self.at_design, self.at_state)
        self.dRdX.T.product(self.at_adjoint, self.primal_work[0])
        self.reduced_grad.plus(self.primal_work[0])

    def product(self, in_vec, out_vec):

        # type check given vectors
        if not isinstance(in_vec, ReducedKKTVector):
            raise TypeError('Multiplying vector is not a ReducedKKTVector')
        if not isinstance(out_vec, ReducedKKTVector):
            raise TypeError('Result vector is not a ReducedKKTVector')

        # calculate appropriate FD perturbation for design
        epsilon_fd = calc_epsilon(self.primal_norm, in_vec._primal.norm2)

        # assemble RHS for first adjoint system
        self.dRdX.linearize(self.at_design, self.at_state)
        self.dRdX.T.product(in_vec._primal, self.state_work[0])
        self.state_work[0].times(-1.0)

        # calculate tolerance for adjoint solution
        #rel_tol = self.product_tol*self.product_fac/self.state_work[0].norm2

        # perform the adjoint solution
        self.w_adj.equals(0.0)
        #self.dRdU.linearize(self.at_design, self.at_state)
        #self.dRdU.solve(self.state_work[0], self.w_adj, rel_tol=rel_tol)
        self._linear_solve(self.state_work[0], self.w_adj, rel_tol=rel_tol)

        # find the adjoint perturbation by solving the linearized dual equation
        self.pert_design.equals_ax_p_by(1.0, self.at_design, epsilon_fd, in_vec._design)
        self.state_work[2].equals_ax_p_by(1.0, self.at_state, epsilon_fd, self.w_adj)

        # first part of LHS: evaluate the adjoint equation residual at
        # perturbed design and state
        self.state_work[0].equals_objective_partial(self.pert_design, self.state_work[2])
        self.dRdU.linearize(self.pert_design, self.state_work[2])
        self.dRdU.T.product(self.at_adjoint, self.state_work[1])
        self.state_work[0].plus(self.state_work[1])
        self.dCdU.linearize(self.pert_design, self.state_work[2])
        self.dCdU.T.product(self.at_dual, self.state_work[1])
        self.state_work[0].plus(self.state_work[1])

        # at this point state_work[0] should contain the perturbed adjoint
        # residual, so take difference with unperturbed adjoint residual
        self.state_work[0].minus(self.adjoint_res)
        self.state_work[0].divide_by(epsilon_fd)

        # multiply by -1 to move to RHS
        self.state_work[0].times(-1.0)

        # second part of LHS: (dC/dU) * in_vec._dual
        self.dCdU.linearize(self.at_design, self.at_state)
        self.dCdU.T.product(in_vec._dual, self.state_work[1])

        # assemble final RHS
        self.state_work[0].minus(self.state_work[1])

        # calculate tolerance for adjoint solution
        #rel_tol = self.product_tol*self.product_fac/self.state_work[0].norm2

        # perform the adjoint solution
        self.lambda_adj.equals(0.0)
        #self.dRdU.linearize(self.at_design, self.at_state)
        #self.dRdU.T.solve(self.state_work[0], self.lambda_adj, rel_tol=rel_tol)
        self._adjoint_solve(self.state_work[0], self.lambda_adj, rel_tol=rel_tol)

        # evaluate first order optimality conditions at perturbed design, state
        # and adjoint:
        # g = df/dX + lag_mult*dC/dX + (state + eps_fd*lambda_adj)*dR/dX
        self.state_work[1].equals_ax_p_by(1.0, self.at_adjoint, epsilon_fd, self.lambda_adj)
        out_vec._primal.equals_objective_partial(self.pert_design, self.state_work[2])
        self.dRdX.linearize(self.pert_design, self.state_work[2])
        self.dRdX.T.product(self.state_work[1], self.primal_work)
        out_vec._primal.plus(self.primal_work)
        self.dCdX.linearize(self.pert_design, self.state_work[2])
        self.dCdX.T.product(self.at_dual, self.primal_work)
        out_vec._primal.plus(self.primal_work)
        self.dCdX.linearize(self.at_design, self.at_state)
        self.dCdX.T.product(in_vec._dual, self.primal_work)
        self.primal_work.times(epsilon_fd)
        out_vec._primal.plus(self.primal_work)

        # take difference with unperturbed conditions
        out_vec._primal.times(self.grad_scale)
        out_vec._primal.minus(self.reduced_grad)
        out_vec._primal.divide_by(epsilon_fd)

        # evaluate dual part of product:
        # C = dC/dX*in_vec + dC/dU*w_adj
        self.dCdX.linearize(self.at_design, self.at_state)
        self.dCdX.product(in_vec._primal, out_vec._dual)
        self.dCdU.linearize(self.at_design, self.at_state)
        self.dCdU.product(self.w_adj, self.dual_work)
        out_vec._dual.plus(self.dual_work)
        out_vec._dual.times(self.ceq_scale)

        # reset the approximation flag
        self.approx = False

    def solve(self, in_vec, out_vec, rel_tol=None):

        # make sure we have a krylov solver
        if self.krylov is None:
            raise AttributeError('krylov solver not set')

        # define the preconditioner
        if self.precond is not None:
            if self.quasi_newton is not None:
                precond = self.quasi_newton.solve
            else:
                raise AttributeError('preconditioner is specified but not set')
        else:
            eye = IdentityMatrix()
            precond = eye.product

        # update the solution tolerance if necessary
        if isinstance(rel_tol, float):
            self.krylov.rel_tol = rel_tol

        # trigger the solution
        return self.krylov.solve(self.product, in_vec, out_vec, precond)

from kona.algorithms.base_algorithm import OptimizationAlgorithm

class PredictorCorrectorCnstr(OptimizationAlgorithm):
    """
    A reduced-space Newton-Krylov algorithm for PDE-governed equality constrained optimization, 
    globalized in a predictor-corrector homotopy path following framework.

    This implementation is loosely based on the predictor-corrector method described by 
    `Brown and Zingg<http://www.sciencedirect.com/science/article/pii/S0021999116301760>`_ for
    nonlinear computational fluid dynamics problems.

    The homotopy map used in this algorithm is given as:

    .. math::
        \\\\mathcal{H}(x, u) = \\mu L(x, u) + (1 - \\mu) \frac{1}{2} \\left[ 
        (x - x_0)^T(x - x_0) - (\\lambda - \\lambda_0)^T(\\lambda - \\lambda_0)

    where :math:`x_0` is the initial design point and :math:`\lambda_0` is the initial Lagrange 
    multipliers.

    Attributes
    ----------
    factor_matrices : bool
        Boolean flag for matrix-based PDE solvers.
    mu, inner_tol, step, nom_dcurv, nom_angl, max_factor, min_factor : float
        Homotopy parameters.
    scale, grad_scale, feas_scale : float
        Optimality metric normalization factors.
    hessian : :class:`~kona.linalg.matrices.hessian.ReducedKKTMatrix`
        Matrix object defining the KKT matrix-vector product.
    precond : :class:`~kona.linalg.matrices.hessian.basic.BaseHessian`-like
        Matrix object defining the approximation to the Hessian inverse.
    krylov : :class:`~kona.linalg.solvers.krylov.FGMRES`
        Krylov solver object used to solve the system defined by the KKT matrix-vector product.
    """

    def __init__(self, primal_factory, state_factory,
                 eq_factory=None, ineq_factory=None, optns=None):
        # trigger base class initialization
        super(PredictorCorrectorCnstr, self).__init__(
            primal_factory, state_factory, eq_factory, ineq_factory, optns
        )

        # number of vectors required in solve() method
        self.primal_factory.request_num_vectors(14)
        self.state_factory.request_num_vectors(5)
        self.eq_factory.request_num_vectors(14)

        # general options
        ############################################################
        self.factor_matrices = get_opt(self.optns, False, 'matrix_explicit')

        # reduced hessian settings
        ############################################################
        self.hessian = ReducedKKTMatrix(
            [self.primal_factory, self.state_factory, self.eq_factory])
        self.mat_vec = self.hessian.product

        # hessian preconditiner settings
        ############################################################
        self.precond = get_opt(self.optns, None, 'rsnk', 'precond')
        self.idf_schur = None
        if self.precond is None:
            # use identity matrix product as preconditioner
            self.eye = IdentityMatrix()
            self.precond = self.eye.product
        elif self.precond is 'idf_schur':
            self.info_file.write("Using IDF-Schur Preconditioner...\n")
            self.eye = IdentityMatrix()
            self.idf_schur = ReducedSchurPreconditioner(
                [primal_factory, state_factory, eq_factory, ineq_factory])
            self.precond = self.eye.product
        else:
            raise BadKonaOption(self.optns, 'rsnk', 'precond')

        # krylov solver settings
        ############################################################
        krylov_optns = {
            'krylov_file'   : get_opt(
                self.optns, 'kona_krylov.dat', 'rsnk', 'krylov_file'),
            'subspace_size' : get_opt(self.optns, 10, 'rsnk', 'subspace_size'),
            'check_res'     : get_opt(self.optns, True, 'rsnk', 'check_res'),
            'rel_tol'       : get_opt(self.optns, 1e-2, 'rsnk', 'rel_tol'),
        }
        self.krylov = FGMRES(self.primal_factory, krylov_optns,
                             eq_factory=self.eq_factory, ineq_factory=None)

        # homotopy options
        ############################################################
        self.mu = 1.0
        self.inner_tol = get_opt(self.optns, 1e-2, 'homotopy', 'inner_tol')
        self.inner_maxiter = get_opt(self.optns, 50, 'homotopy', 'inner_maxiter')
        self.step = get_opt(self.optns, 0.1, 'homotopy', 'init_step')
        self.nom_dcurve = get_opt(self.optns, 1.0, 'homotopy', 'nominal_dist')
        self.nom_angl = get_opt(self.optns, 5.0*np.pi/180., 'homotopy', 'nominal_angle')
        self.max_factor = get_opt(self.optns, 2.0, 'homotopy', 'max_factor')
        self.min_factor = get_opt(self.optns, 0.5, 'homotopy', 'min_factor')
        self.max_step = get_opt(self.optns, 0.2, 'homotopy', 'max_step')
        self.idf_hom = get_opt(self.optns, False, 'homotopy', 'idf_hom')
        self.hom_weight = get_opt(self.optns, 1., 'homotopy', 'weight')

    def _write_header(self, opt_tol, feas_tol):
        self.hist_file.write(
            '# Kona Param. Contn. convergence history ' +
            '(opt tol = %e | feas tol = %e)\n'%(opt_tol, feas_tol) +
            '# outer' + ' '*5 +
            'inner' + ' '*5 +
            ' cost' + ' '*5 +
            ' objective' + ' ' * 5 +
            'lagrangian' + ' ' * 5 +
            '  opt norm' + ' '*5 +
            ' feas norm' + ' '*5 +
            '   hom opt' + ' '*5 +
            '  hom feas' + ' '*5 +
            'mu        ' + ' '*5 +
            '\n'
        )

    def _write_outer(self, outer, obj, lag, opt_norm, feas_norm):
        if obj < 0.:
            obj_fmt = '%.3e'%obj
        else:
            obj_fmt = ' %.3e'%obj
        if lag < 0.:
            lag_fmt = '%.3e'%lag
        else:
            lag_fmt = ' %.3e'%lag
        self.hist_file.write(
            '%7i' % outer + ' ' * 5 +
            '-'*5 + ' ' * 5 +
            '%5i' % self.primal_factory._memory.cost + ' ' * 5 +
            obj_fmt + ' ' * 5 +
            lag_fmt + ' ' * 5 +
            '%.4e' % opt_norm + ' ' * 5 +
            '%.4e' % feas_norm + ' ' * 5 +
            '-'*10 + ' ' * 5 +
            '-'*10 + ' ' * 5 +
            '%1.4f' % self.mu + ' ' * 5 +
            '\n'
        )

    def _write_inner(self, outer, inner, 
                     obj, lag, opt_norm, feas_norm,
                     hom_opt, hom_feas):
        if obj < 0.:
            obj_fmt = '%.3e'%obj
        else:
            obj_fmt = ' %.3e'%obj
        if lag < 0.:
            lag_fmt = '%.3e'%lag
        else:
            lag_fmt = ' %.3e'%lag
        self.hist_file.write(
            '%7i' % outer + ' ' * 5 +
            '%5i' % inner + ' ' * 5 +
            '%5i' % self.primal_factory._memory.cost + ' ' * 5 +
            obj_fmt + ' ' * 5 +
            lag_fmt + ' ' * 5 +
            '%.4e' % opt_norm + ' ' * 5 +
            '%.4e' % feas_norm + ' ' * 5 +
            '%.4e' % hom_opt + ' ' * 5 +
            '%.4e' % hom_feas + ' ' * 5 +
            '%1.4f' % self.mu + ' ' * 5 +
            '\n'
        )

    def _generate_primal(self):
        return self.primal_factory.generate()

    def _generate_dual(self):
        return self.eq_factory.generate()

    def _generate_kkt(self):
        primal = self._generate_primal()
        dual = self._generate_dual()
        return ReducedKKTVector(primal, dual)

    def _mat_vec(self, in_vec, out_vec):
        out_vec.equals(0.0)
        self.hessian.product(in_vec, out_vec)

        if self.idf_hom:
            out_vec.times(1. - self.mu)
        else:
            self.prod_work1.equals(1. - self.mu)
            self.prod_work1.primal.restrict_to_design()
            self.prod_work1.dual.restrict_to_regular()
            self.prod_work2.equals(1.0)
            self.prod_work2.primal.restrict_to_target()
            self.prod_work2.dual.restrict_to_idf()
            self.prod_work2.plus(self.prod_work1)
            out_vec.times(self.prod_work2)

        self.prod_work2.primal.equals(self.mu)
        self.prod_work2.dual.equals(-self.mu)
        self.prod_work2.primal.restrict_to_design()
        self.prod_work2.dual.restrict_to_regular()
        self.prod_work1.equals(in_vec)
        self.prod_work1.times(self.hom_weight)
        self.prod_work1.times(self.prod_work2)
        out_vec.plus(self.prod_work1)

        if self.idf_hom:
            self.prod_work1.equals(0.0)
            self.prod_work1.dual.equals(in_vec.dual)
            self.prod_work1.dual.convert_to_design(self.prod_work1.primal)
            self.prod_work1.primal.times(self.mu*self.hom_weight)
            self.prod_work1.primal.restrict_to_target()
            out_vec.primal.minus(self.prod_work1.primal)

            self.prod_work1.equals(0.0)
            self.prod_work1.primal.equals(in_vec.primal)
            self.prod_work1.primal.convert_to_dual(self.prod_work1.dual)
            self.prod_work1.dual.times(self.mu*self.hom_weight)
            self.prod_work1.dual.restrict_to_idf()
            out_vec.dual.minus(self.prod_work1.dual)

    def solve(self):
        self.info_file.write(
            '\n' +
            '**************************************************\n' +
            '***        Using Parameter Continuation        ***\n' +
            '**************************************************\n' +
            '\n')

        # get the vectors we need
        x = self._generate_kkt()
        x0 = self._generate_kkt()
        x_save = self._generate_kkt()
        dJdX = self._generate_kkt()
        dJdX_save = self._generate_kkt()
        dJdX_hom = self._generate_kkt()
        dx = self._generate_kkt()
        dx_newt = self._generate_kkt()
        rhs_vec = self._generate_kkt()
        t = self._generate_kkt()
        t_save = self._generate_kkt()
        self.prod_work1 = self._generate_kkt()
        self.prod_work2 = self._generate_kkt()

        state = self.state_factory.generate()
        state_work = self.state_factory.generate()
        state_save = self.state_factory.generate()
        adj = self.state_factory.generate()
        adj_save = self.state_factory.generate()

        primal_work = self._generate_primal()

        dual_work = self._generate_dual()

        self.info_file.write(
            '# of design vars = %i\n' % len(primal_work.base.data) +
            '# of eq cnstr    = %i\n' % len(dual_work.base.data) +
            '\n'
        )

        # initialize the problem at the starting point
        x0.equals_init_guess()
        x.equals(x0)
        if not state.equals_primal_solution(x.primal):
            raise RuntimeError('Invalid initial point! State-solve failed.')
        if self.factor_matrices:
            factor_linear_system(x.primal, state)

        # compute scaling factors
        adj_save.equals_objective_adjoint(x.primal, state, state_work)
        primal_work.equals_total_gradient(x.primal, state, adj_save)
        obj_norm0 = primal_work.norm2
        obj_fac = 1./obj_norm0
        # dual_work.equals_constraints(x.primal, state)
        # cnstr_norm0 = dual_work.norm2
        cnstr_fac = 1.

        # compute the lagrangian adjoint
        adj.equals_lagrangian_adjoint(
            x, state, state_work, obj_scale=obj_fac, cnstr_scale=cnstr_fac)

        # compute initial KKT conditions
        dJdX.equals_KKT_conditions(
            x, state, adj, obj_scale=obj_fac, cnstr_scale=cnstr_fac)

        # send solution to solver
        solver_info = current_solution(
            num_iter=0, curr_primal=x.primal,
            curr_state=state, curr_adj=adj, curr_dual=x.dual)
        if isinstance(solver_info, str) and solver_info != '':
            self.info_file.write('\n' + solver_info + '\n')

        # compute convergence metrics
        opt_norm0 = dJdX.primal.norm2
        feas_norm0 = dJdX.dual.norm2
        opt_tol = self.primal_tol
        feas_tol = self.cnstr_tol
        self._write_header(opt_tol, feas_tol)

        # write the initial point
        obj0 = objective_value(x.primal, state)
        lag0 = obj_fac * obj0 + cnstr_fac * x0.dual.inner(dJdX.dual)
        self._write_outer(0, obj0, lag0, opt_norm0, feas_norm0)
        self.hist_file.write('\n')

        # compute the rhs vector for the predictor problem
        rhs_vec.equals(dJdX)
        rhs_vec.times(-1.)

        if not self.idf_hom:
            rhs_vec.primal.restrict_to_design() 
            rhs_vec.dual.restrict_to_regular()

        self.prod_work2.primal.equals(1.0)
        self.prod_work2.dual.equals(-1.0)
        self.prod_work2.primal.restrict_to_design()
        self.prod_work2.dual.restrict_to_regular()
        self.prod_work1.equals(x)
        self.prod_work1.minus(x0)
        self.prod_work1.times(self.hom_weight)
        self.prod_work1.times(self.prod_work2)
        rhs_vec.plus(self.prod_work1)

        if self.idf_hom:
            dual_work.equals(x.dual)
            dual_work.restrict_to_idf()
            primal_work.equals(0.0)
            dual_work.convert_to_design(primal_work)
            primal_work.restrict_to_target()
            primal_work.times(self.hom_weight)
            rhs_vec.primal.minus(primal_work)

            primal_work.equals(x.primal)
            primal_work.minus(x0.primal)
            primal_work.restrict_to_target()
            dual_work.equals(0.0)
            primal_work.convert_to_dual(dual_work)
            dual_work.restrict_to_idf()
            dual_work.times(self.hom_weight)
            rhs_vec.dual.minus(dual_work)

        # compute the tangent vector
        t.equals(0.0)
        self.hessian.linearize(
            x, state, adj,
            obj_scale=obj_fac, cnstr_scale=cnstr_fac)
        if self.idf_schur is not None:
            if self.idf_hom:
                self.idf_schur.linearize(
                    x.primal, state, scale=cnstr_fac, homotopy=self.mu)
                self.precond = self.idf_schur.product
            else:
                self.idf_schur.linearize(x.primal, state, scale=cnstr_fac, homotopy=0.0)
                self.precond = self.idf_schur.product
        self.krylov.solve(self._mat_vec, rhs_vec, t, self.precond)

        # normalize tangent vector
        tnorm = np.sqrt(t.inner(t) + 1.0)
        t.times(1./tnorm)
        dmu = -1./tnorm

        # START OUTER ITERATIONS
        #########################
        outer_iters = 1
        total_iters = 0
        while self.mu > 0.0 and outer_iters <= self.max_iter:

            self.info_file.write(
                '==================================================\n')
            self.info_file.write(
                'Outer Homotopy iteration %i\n'%(outer_iters))
            self.info_file.write('\n')

            dJdX.equals_KKT_conditions(
                x, state, adj,
                obj_scale=obj_fac, cnstr_scale=cnstr_fac)
            opt_norm = dJdX.primal.norm2
            feas_norm = dJdX.dual.norm2
            self.info_file.write(
                'opt_norm : opt_tol = %e : %e\n'%(
                    opt_norm, opt_tol) +
                'feas_norm : feas_tol = %e : %e\n' % (
                    feas_norm, feas_tol))

            # save current solution in case we need to revert
            x_save.equals(x)
            state_save.equals(state)
            adj_save.equals(adj)
            dJdX_save.equals(dJdX)
            t_save.equals(t)
            dmu_save = dmu
            mu_save = self.mu

            # take a predictor step
            x.equals_ax_p_by(1.0, x, self.step, t)
            self.mu += dmu*self.step
            if self.mu < 0.0:
                self.mu = 0.0
            self.info_file.write('\nmu after pred  = %f\n'%self.mu)

            # solve states
            if not state.equals_primal_solution(x.primal):
                raise RuntimeError(
                    'Invalid predictor point! State-solve failed.')
            if self.factor_matrices:
                factor_linear_system(x.primal, state)

            # compute adjoint
            adj.equals_lagrangian_adjoint(
                x, state, state_work, obj_scale=obj_fac, cnstr_scale=cnstr_fac)

            # START CORRECTOR (Newton) ITERATIONS
            #####################################
            max_newton = self.inner_maxiter
            inner_iters = 0
            dx_newt.equals(0.0)
            for i in xrange(max_newton):

                self.info_file.write('\n')
                self.info_file.write('   Inner Newton iteration %i\n'%(i+1))
                self.info_file.write('   -------------------------------\n')

                # compute the KKT conditions
                dJdX.equals_KKT_conditions(
                    x, state, adj,
                    obj_scale=obj_fac, cnstr_scale=cnstr_fac)
                dJdX_hom.equals(dJdX)

                # get the lagrangian component of the homotopy
                if self.idf_hom:
                    dJdX_hom.times(1. - self.mu)
                else:
                    self.prod_work1.equals(1. - self.mu)
                    self.prod_work1.primal.restrict_to_design()
                    self.prod_work1.dual.restrict_to_regular()
                    self.prod_work2.equals(1.0)
                    self.prod_work2.primal.restrict_to_target()
                    self.prod_work2.dual.restrict_to_idf()
                    self.prod_work2.plus(self.prod_work1)
                    dJdX_hom.times(self.prod_work2)

                # get the regularization component of the homotopy
                self.prod_work2.primal.equals(self.mu)
                self.prod_work2.dual.equals(-self.mu)
                self.prod_work2.primal.restrict_to_design()
                self.prod_work2.dual.restrict_to_regular()
                self.prod_work1.equals(x)
                self.prod_work1.minus(x0)
                self.prod_work1.times(self.hom_weight)
                self.prod_work1.times(self.prod_work2)
                dJdX_hom.plus(self.prod_work1)

                if self.idf_hom:
                    # add the IDF homotopy contribution to dJdX.primal
                    # NOTE: this does nothing if the problem is not IDF
                    dual_work.equals(x.dual)
                    dual_work.restrict_to_idf()
                    dual_work.times(self.mu*self.hom_weight)
                    primal_work.equals(0.0)
                    dual_work.convert_to_design(primal_work)
                    primal_work.restrict_to_target()
                    dJdX_hom.primal.minus(primal_work)

                    # add the IDF homotopy contribution to dJdX.dual
                    # NOTE: this does nothing if the problem is not IDF
                    primal_work.equals(x.primal)
                    primal_work.minus(x0.primal)
                    primal_work.restrict_to_target()
                    primal_work.times(self.mu*self.hom_weight)
                    dual_work.equals(0.0)
                    primal_work.convert_to_dual(dual_work)
                    dual_work.restrict_to_idf()
                    dJdX_hom.dual.minus(dual_work)

                # get convergence norms
                if inner_iters == 0:
                    # compute optimality norms
                    hom_opt_norm0 = dJdX_hom.primal.norm2
                    hom_opt_norm = hom_opt_norm0
                    hom_opt_tol = self.inner_tol * hom_opt_norm0
                    if hom_opt_tol < opt_tol or self.mu == 0.0:
                        hom_opt_tol = opt_tol
                    # compute feasibility norms
                    hom_feas_norm0 = dJdX_hom.dual.norm2
                    hom_feas_norm = hom_feas_norm0
                    hom_feas_tol = self.inner_tol * hom_feas_norm0
                    if hom_feas_tol < feas_tol or self.mu == 0.0:
                        hom_feas_tol = feas_tol
                else:
                    hom_opt_norm = dJdX_hom.primal.norm2
                    hom_feas_norm = dJdX_hom.dual.norm2
                self.info_file.write(
                    '   hom_opt_norm : hom_opt_tol = %e : %e\n'%(
                        hom_opt_norm, hom_opt_tol) +
                    '   hom_feas_norm : hom_feas_tol = %e : %e\n'%(
                        hom_feas_norm, hom_feas_tol))

                # write inner history
                obj = objective_value(x.primal, state)
                lag = obj + x.dual.inner(dJdX.dual)
                opt_norm = dJdX.primal.norm2
                feas_norm = dJdX.dual.norm2
                self._write_inner(
                    outer_iters, inner_iters,
                    obj, lag, opt_norm, feas_norm,
                    hom_opt_norm, hom_feas_norm)

                # check convergence
                if hom_opt_norm <= hom_opt_tol and hom_feas_norm <= hom_feas_tol:
                    self.info_file.write('\n   Corrector step converged!\n')
                    break

                # linearize the hessian at the new point
                self.hessian.linearize(
                    x, state, adj,
                    obj_scale=obj_fac, cnstr_scale=cnstr_fac)
                if self.idf_schur is not None:
                    if self.idf_hom:
                        self.idf_schur.linearize(
                            x.primal, state, scale=cnstr_fac, homotopy=self.mu)
                        self.precond = self.idf_schur.product
                    else:
                        self.idf_schur.linearize(
                            x.primal, state, scale=cnstr_fac, homotopy=0.0)
                        self.precond = self.idf_schur.product

                # define the RHS vector for the homotopy system
                dJdX_hom.times(-1.)

                # solve the system
                dx.equals(0.0)
                self.krylov.solve(self._mat_vec, dJdX_hom, dx, self.precond)
                dx_newt.plus(dx)

                # update the design
                x.plus(dx)
                if not state.equals_primal_solution(x.primal):
                    raise RuntimeError('Newton step failed!')
                if self.factor_matrices:
                    factor_linear_system(x.primal, state)

                # compute the adjoint
                adj.equals_lagrangian_adjoint(
                    x, state, state_work, obj_scale=obj_fac, cnstr_scale=cnstr_fac)

                # advance iter counter
                inner_iters += 1
                total_iters += 1

            # if we finished the corrector step at mu=1, we're done!
            if self.mu == 0.0:
                self.info_file.write('\n>> Optimization DONE! <<\n')
                # send solution to solver
                solver_info = current_solution(
                    num_iter=outer_iters, curr_primal=x.primal,
                    curr_state=state, curr_adj=adj, curr_dual=x.dual)
                if isinstance(solver_info, str) and solver_info != '':
                    self.info_file.write('\n' + solver_info + '\n')
                return

            # COMPUTE NEW TANGENT VECTOR
            ############################

            # assemble the predictor RHS
            rhs_vec.equals(dJdX)
            rhs_vec.times(-1.)

            if not self.idf_hom:
                rhs_vec.primal.restrict_to_design()
                rhs_vec.dual.restrict_to_regular()

            self.prod_work2.primal.equals(1.0)
            self.prod_work2.dual.equals(-1.0)
            self.prod_work2.primal.restrict_to_design()
            self.prod_work2.dual.restrict_to_regular()
            self.prod_work1.equals(x)
            self.prod_work1.minus(x0)
            self.prod_work1.times(self.hom_weight)
            self.prod_work1.times(self.prod_work2)
            rhs_vec.plus(self.prod_work1)

            if self.idf_hom:
                dual_work.equals(x.dual)
                dual_work.restrict_to_idf()
                primal_work.equals(0.0)
                dual_work.convert_to_design(primal_work)
                primal_work.restrict_to_target()
                primal_work.times(self.hom_weight)
                rhs_vec.primal.minus(primal_work)

                primal_work.equals(x.primal)
                primal_work.minus(x0.primal)
                primal_work.restrict_to_target()
                dual_work.equals(0.0)
                primal_work.convert_to_dual(dual_work)
                dual_work.restrict_to_idf()
                dual_work.times(self.hom_weight)
                rhs_vec.dual.minus(dual_work)

            # compute the new tangent vector and predictor step
            t.equals(0.0)
            self.hessian.linearize(
                x, state, adj,
                obj_scale=obj_fac, cnstr_scale=cnstr_fac)
            if self.idf_schur is not None:
                if self.idf_hom:
                    self.idf_schur.linearize(
                        x.primal, state, scale=cnstr_fac, homotopy=self.mu)
                    self.precond = self.idf_schur.product
                else:
                    self.idf_schur.linearize(
                        x.primal, state, scale=cnstr_fac, homotopy=0.0)
                    self.precond = self.idf_schur.product
            self.krylov.solve(self._mat_vec, rhs_vec, t, self.precond)

            # normalize the tangent vector
            tnorm = np.sqrt(t.inner(t) + 1.0)
            t.times(1./tnorm)
            dmu = -1./tnorm

            # compute distance to curve
            self.info_file.write('\n')
            dcurve = dx_newt.norm2
            self.info_file.write(
                'dist to curve = %e\n' % dcurve)

            # compute angle between steps
            uTv = t.inner(t_save) + (dmu * dmu_save)
            angl = np.arccos(uTv)
            self.info_file.write(
                'angle         = %f\n' % (angl * 180. / np.pi))

            # compute deceleration factor
            dfac = max(np.sqrt(dcurve / self.nom_dcurve), angl / self.nom_angl)
            dfac = max(min(dfac, self.max_factor), self.min_factor)

            # apply the deceleration factor
            self.info_file.write('factor        = %f\n' % dfac)
            self.step /= dfac
            self.info_file.write('step len      = %f\n' % self.step)

            # if factor is bad, go back to the previous point with new factor
            if dfac == self.max_factor:
                self.info_file.write(
                    'High curvature! Rejecting solution...\n')
                # revert solution
                x.equals(x_save)
                self.mu = mu_save
                t.equals(t_save)
                dmu = dmu_save
                state.equals(state_save)
                adj.equals(adj_save)
                dJdX.equals(dJdX_save)
                if self.factor_matrices:
                    factor_linear_system(x.primal, state)
            else:
                # this step is accepted so send it to user
                solver_info = current_solution(
                    num_iter=outer_iters, curr_primal=x.primal,
                    curr_state=state, curr_adj=adj, curr_dual=x.dual)
                if isinstance(solver_info, str) and solver_info != '':
                    self.info_file.write('\n' + solver_info + '\n')

            # advance iteration counter
            outer_iters += 1
            self.info_file.write('\n')
            self.hist_file.write('\n')

# imports here to prevent circular errors
import numpy as np
from kona.options import BadKonaOption, get_opt
from kona.linalg.common import current_solution, factor_linear_system, objective_value
from kona.linalg.vectors.composite import ReducedKKTVector
from kona.linalg.matrices.common import IdentityMatrix
from kona.linalg.matrices.hessian import ReducedKKTMatrix
from kona.linalg.matrices.preconds import ReducedSchurPreconditioner
from kona.linalg.solvers.krylov import FGMRES
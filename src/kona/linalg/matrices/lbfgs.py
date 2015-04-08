from quasi_newton import QuasiNewtonApprox
import numpy
import sys


class LimitedMemoryBFGS(QuasiNewtonApprox):
    """ Limited-memory BFGS
    
    Attributes
    ----------
    lambda0 : float
        ?
    s_dot_s_list : list of floats
        the two-norm of the step vector
    s_dot_y_list : list of floats
        curvature
    """

    def __init__(self, vector_factory, optns, out_file=sys.stdout):
        super(LimitedMemoryBFGS, self).__init__(vector_factory, optns, out_file)

        self.lambda0 = 0
        self.s_dot_s_list = []
        self.s_dot_y_list = []

        vector_factory.request_num_vectors(2*optns['max_stored'])

    def add_correction(self, s_in, y_in):
        """
        Add the step, change in gradient, curvature, and two-norm
        to the lists storing the history.
        """
        two_norm = s_in.inner(s_in)
        curvature = s_in.inner(y_in)

        if curvature < numpy.finfo(float).eps:
            self.out_file.write('LimitedMemoryBFGS::AddCorrection():' +
                                'correction skipped due to curvature condition.')
            return

        s_new = self.vec_fac.generate()
        y_new = self.vec_fac.generate()

        s_new.equals(s_in)
        y_new.equals(y_in)

        if len(self.s_list) == self.max_stored:
            del self.s_list[0]
            del self.y_list[0]
            del self.s_dot_s_list[0]
            del self.s_dot_y_list[0]

        self.s_list.append(s_new)
        self.y_list.append(y_new)
        self.s_dot_s_list.append(two_norm)
        self.s_dot_y_list.append(curvature)

    def solve(self, u_vec, v_vec, rel_tol=1e-15):
        lambda0 = self.lambda0
        s_list = self.s_list
        y_list = self.y_list
        s_dot_s_list = self.s_dot_s_list
        s_dot_y_list = self.s_dot_y_list

        num_stored = len(s_list)
        rho = numpy.zeros(num_stored)
        alpha = numpy.zeros(num_stored)

        for k in xrange(num_stored):
            rho[k] = 1.0 / (s_dot_s_list[k] * lambda0 +
                            s_dot_y_list[k])

        v_vec.equals(u_vec)
        for k in xrange(num_stored-1, -1, -1):
            alpha[k] = rho[k] * s_list[k].inner(v_vec)
            if lambda0 > 0.0:
                v_vec.equals_ax_p_by(1.0, v_vec,
                                     -alpha[k] * lambda0, s_list[k])
            v_vec.equals_ax_p_by(1.0, v_vec, -alpha[k], y_list[k])

        if num_stored > 0:
            k = num_stored - 1
            yTy = y_list[k].inner(y_list[k])
            if lambda0 > 0.0:
                yTy += 2.0 * lambda0 * s_dot_y_list[k]
                yTy += lambda0 * lambda0 * s_dot_s_list[k]
            scale = 1.0 / (rho[k] * yTy)
            v_vec.times(scale)
        else:
            v_vec.divide(self.norm_init)

        for k in xrange(num_stored):
            beta = rho[k] * y_list[k].inner(v_vec)
            if lambda0 > 0.0:
                beta += rho[k] * lambda0 * s_list[k].inner(v_vec)
            v_vec.equals_ax_p_by(1.0, v_vec, (alpha[k] - beta), s_list[k])